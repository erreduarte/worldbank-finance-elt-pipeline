from datetime import datetime
import requests
import pandas as pd
from airflow.providers.microsoft.azure.hooks.wasb import WasbHook
from airflow.providers.microsoft.mssql.hooks.mssql import MsSqlHook 
import io
from airflow.decorators import dag, task

#Dag bag
@dag(schedule=None,
     start_date = datetime(2024, 9, 25),
     catchup = False,
     default_args={ 
         'owner': 'erre_duarte',
     },
     description="Extract data from World Bank API, transform it and load it to Azure Database",
     tags = ['WorldBank', 'ELT']
    )


def ELT_WB():

    @task 
    def fetch_WB_data():      
        
         
        try:
            #WorlBank public API address. 
            #Limiting data extraction to just 50,000 rows due to further limitation with platforms free tier.
            url = 'https://finances.worldbank.org/resource/zucq-nrc3.json?$limit=50000' 

        #Fetch data from the API
            response = requests.get(url)
            response.raise_for_status()  # Raise response from API
        
        #Parse JSON data
            data = response.json()
        
        #Transform it in a dataframe
            df_bronze = pd.DataFrame(data)

        #Hold file in memory
            csv_buffer = io.StringIO()
            df_bronze.to_csv(csv_buffer, index=False)

        #Blob Path
            blob_container = "rfd-container"
            blob_name = "WB_Data_Loans__Bronze.csv"

        #Save dataframe in Blob Storage
            hook = WasbHook(wasb_conn_id='azure_blob_storage')
            hook.load_string(string_data = csv_buffer.getvalue(), 
                         container_name=blob_container, 
                         blob_name=blob_name, 
                         overwrite=True)
            
        #Raise error message, if applicable    
        except Exception as e:
            print(f'Error fetching data: {e}')             
        #Raise completion message, if successful   
        finally:
            return {"message:" f"Data successfully transformed. Saved in blob storage as {blob_container}/{blob_name}"}
        
    @task     
    def transform_WB_data():
       
        #Connection credentials to Blob Storage
        hook = WasbHook(wasb_conn_id = 'azure_blob_storage')

        try:
            #Read file from Blob Storage 
            blob_file = hook.read_file(container_name = "rfd-container", blob_name = "WB_Data_Loans__Bronze.csv")
            blob_file_io = io.StringIO(blob_file) 
            df = pd.read_csv(blob_file_io)

            #Selection of only necessary columns and transformation of file into a pandas dataframe for data transformations 
            df_silver = df[["loan_number", "region", "country", "loan_status", 
                        "original_principal_amount", "repaid_to_ibrd", "repaid_3rd_party", 
                        "undisbursed_amount"]] 


            #Clean up        
            columns_to_clean = ['loan_number', 'region', 'country', 'loan_status']

            for col in columns_to_clean:
                df_silver[col] = df_silver[col].str.replace(r'[\$,]+', '', regex=True) #Remove dollar signs and commas to prepare data to MSSQL
                df_silver[col] = df_silver[col].str.replace(r'\s+', ' ', regex=True) #Remove double spaces
                df_silver[col] = df_silver[col].str.replace("'", "") #Remove single quotes
                df_silver[col] = df_silver[col].str.strip()
                df_silver[col] = df_silver[col].str.upper() #Conver text to upper case for consistency

            #Create calculated columns for further analysis 
            df_silver["total_repaid"] = df_silver["repaid_to_ibrd"].fillna(0) + df_silver["repaid_3rd_party"].fillna(0) 
            df_silver["debt_remaining"] = df_silver["original_principal_amount"].fillna(0) - df_silver["total_repaid"].fillna(0)

            #Save clean file into Blob Storage as "SILVER" version
            csv_buffer = io.StringIO() 
            df_silver.to_csv(csv_buffer, index = False)
            blob_container = "rfd-container"
            blob_name = "WB_Data_Loans__Silver.csv"
            hook.load_string(string_data = csv_buffer.getvalue(), 
                            container_name=blob_container, 
                            blob_name= blob_name,
                            overwrite = True)
        
        #Raise error messages, if applicable    
        except Exception as e:
            print(f"Error {str(e)}")
        #Raise message upon completion
        finally:
            return {f"Data successfully transformed. Saved in blob storage as {blob_container}/{blob_name}"}
         
    @task
    def create_MS_SQL_table():
        #Azure Database Credentials
        hook = MsSqlHook(mssql_conn_id = "microsoft_azure_database")
        #Drop table if exists (necessary due to FreeTier limitations)
        drop_table_sql = """
            DROP TABLE IF EXISTS dbo.WB_Loans; """
        #Create table
        create_table_sql = """
            
                CREATE TABLE dbo.WB_Loans (
                loan_number              VARCHAR(10),
                region                   VARCHAR(30),
                country                  VARCHAR(30),
                loan_status              VARCHAR(15),
                original_principal_amount FLOAT,
                repaid_to_ibrd           FLOAT,
                repaid_3rd_party         FLOAT,
                undisbursed_amount       FLOAT,
                total_repaid             FLOAT,
                debt_remaining           FLOAT
                )
        """
        #Run queries
        try:
            #Run query DROP TABLE IF EXISTS
            hook.run(drop_table_sql)
            print("Table dbo.WB_Loans sucessfully dropped or didn't exist")
            #Run query CREATE TABLE
            hook.run(create_table_sql)
            print("Table sucessfully created")
            return "Table dbo.WB_Loans sucessfully created"
        #Error messages, if applicable
        except Exception as e:
            print(f"Error { str(e)}")
            raise 
    
    @task
    def populate_dbo_WB_Loans():
        #Azure Database Credentials
        hook = MsSqlHook(mssql_conn_id = "microsoft_azure_database")
        #SQL Bulk load file into new table. A MASTER KEY, DATABASE SCOPED CREDENTIALS and EXTERNAL DATA SOURCE was previously created in Azure Portal. 
        populate_sql =  """
                BULK INSERT dbo.WB_Loans
                FROM 'WB_Data_Loans__Silver.csv'
                WITH (
                    DATA_SOURCE     = 'WorldBankData',
                    ROWTERMINATOR   = '0x0a',
                    FIELDTERMINATOR = ',',
                    FIRSTROW        = 2
                );
            """
        try:
            #Run populate_sql query
            hook.run(populate_sql)
            print("Table sucessfully populated")
            
            #Select count of rows loaded into table.
            count_rows_sql = "SELECT COUNT (*) FROM dbo.WB_Loans"

            #Return the results from count query.
            rows = hook.get_records(count_rows_sql)[0][0] #Accessing count from tuple-list
            return f"The table was created and contains {rows} rows"
        
        #Raise error message, if applicable
        except Exception as e:
            print(f"Error { str(e)}")
            raise                

#Analysis
    @task
    def analysis_regions():

        try:
            #Azure Database credentials 
            hook = MsSqlHook(mssql_conn_id = "microsoft_azure_database")

            #Query to return the regions with the highest loan debts 
            sql = """ 
            SELECT region, CAST(ROUND(SUM(debt_remaining), 2) AS FLOAT) AS debt_remaining 
            FROM dbo.WB_Loans wl 
            GROUP BY region 
            ORDER BY debt_remaining DESC;

        """
            #Using function .get_pandas_df to catch the results
            df = hook.get_pandas_df(sql)

            #Transform the results into a dictionary and return it
            tbl_dct = df.to_dict('dict')
            return f"The results of the query are {tbl_dct}"
        
        #Raise error message, if applicable
        except Exception as e:
            print(f"Error {str(e)}")
            raise

    @task
    def analysis_countries():
        
        try:
            #Azure Database credentials
            hook = MsSqlHook(mssql_conn_id = "microsoft_azure_database")
            
            #Query to return the rank of countries with highest loan debts per region
            sql = """ 
                WITH sum_debt AS (
                SELECT region, country, SUM(debt_remaining) AS debt_remaining
                FROM dbo.WB_Loans wl 
                GROUP BY region, country
            ),
                ranked_debt AS (
                SELECT region, country, ROUND(debt_remaining, 2) AS debt_remaining, 
                RANK() OVER (PARTITION BY region ORDER BY debt_remaining DESC) AS rank
                FROM sum_debt
            )

                SELECT region, country, debt_remaining
                FROM ranked_debt
                WHERE rank = 1 AND debt_remaining <> 0
                ORDER BY debt_remaining DESC;

            """
            
            #Using function .get_pandas_df to catch the results
            df = hook.get_pandas_df(sql)

            #Transform the results into a dictionary and return it
            tbl_dct = df.to_dict('dict')
            return f"The results of the query are {tbl_dct}"
        
        #Raise error message, if applicable
        except Exception as e:
            print(f"Error {str(e)}")
            raise

    @task
    def analysis_loans():

        #Azure Database Credentials
        hook = MsSqlHook(mssql_conn_id = "microsoft_azure_database")
        
        #Query to return the countries with highest number of active loan debts
        sql = """ 
        SELECT TOP 10 country, COUNT(DISTINCT loan_number) AS count_of_loans 
        FROM dbo.WB_Loans wl  
        WHERE debt_remaining > 0 AND loan_status <> 'Fully Paid'
        GROUP BY country
        ORDER BY count_of_loans DESC;
    """
        try:
            #Using function .get_pandas_df to catch the results
            df = hook.get_pandas_df(sql)
            #Transform the results into a dictionary and return it
            tbl_dict = df.to_dict('dict')
            return f"The results of the query are {tbl_dict}"
        
        #Raise error messages, if applicable
        except Exception as e:
            print(f"Error { str(e)}")
            raise



   #Dependencies
    Fetch_Data = fetch_WB_data()
    Transform_Data = transform_WB_data()
    Create_table = create_MS_SQL_table()
    Populate_table = populate_dbo_WB_Loans()
    Analyze_Regions = analysis_regions()
    Analyze_Countries = analysis_countries()
    Analyze_Loans = analysis_loans()

    Fetch_Data >> Transform_Data >> Create_table >> Populate_table >> [Analyze_Regions, Analyze_Countries, Analyze_Loans]
    


ELT_WB()

      
