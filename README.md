# ELT Automation: World Bank API Finance Data to Azure SQL Database

## Overview

This repository showcases an end-to-end **ELT pipeline** designed to extract financial data from the **World Bank API**, transform it using **Pandas**, and load it into an **Azure SQL Database**. The project demonstrates expertise in cloud-native data engineering, focusing on data extraction, transformation, loading, and automation using **Apache Airflow**.

The primary goal of this project is to illustrate how to design and orchestrate scalable ELT pipelines entirely in the cloud, ensuring no files are stored locally. The solution leverages **Azure Blob Storage** for staging data and **Azure SQL Database** for storing cleaned and transformed datasets.

## About the Data

The data used in this project is sourced from the **World Bank's historical loan data**, which tracks loans provided to countries globally. Specifically, it includes information about loans made by the **International Bank for Reconstruction and Development (IBRD)**. These loans are public or publicly guaranteed and are extended to member countries. The data is in USD and uses historical exchange rates.

**Key Information about the Dataset**:
- **Loan History**: Tracks loans by IBRD since 1947.
- **Currency**: Data in USD, reflecting historical market rates.
- **Scope**: Global data covering numerous countries and regions.
- **Latest Snapshot**: This dataset includes historical and up-to-date loan information.

## Key Concepts

- **Data Source**: [World Bank Finance Data API](https://financesone.worldbank.org/ibrd-statement-of-loans-and-guarantees-historical-data/DS00975)
- **Storage**: **Azure Blob Storage** for intermediate staging of extracted and transformed data.
- **Database**: **Azure SQL Database (MSSQL)** for the final storage of cleaned data.
- **Transformation**: Data cleaning, manipulation, and feature engineering using **Pandas**.
- **Orchestration**: Task scheduling and automation using **Apache Airflow**.

## Tools & Technologies

- **Apache Airflow**: Manages the orchestration and automation of the ELT pipeline.
- **Pandas**: Used for data transformation, cleaning, and enrichment.
- **Azure Services**: 
    - **Blob Storage**: Stores raw and transformed data.
    - **SQL Database**: Stores transformed data for analysis.
- **Airflow Providers**: 
    - **WasbHook**: Connects to Azure Blob Storage.
    - **MsSqlHook**: Connects to Azure SQL Database for loading data.

## ELT Process (Code Overview)

### **Extraction**:
- Data is extracted from the **World Bank Finance API** using Python’s **requests** library.
- Due to resource constraints (free-tier limitations), the data extraction is limited to **50,000 rows**.

```python
url = 'https://finances.worldbank.org/resource/zucq-nrc3.json?$limit=50000'
response = requests.get(url)
data = response.json()
df_bronze = pd.DataFrame(data)
```

- The extracted data is stored as a CSV file in Azure Blob Storage.


## Transformations

**The raw data undergoes several transformation steps:**
- Cleaning: Unwanted characters (e.g., dollar signs and commas) are removed.
- Normalization: Text fields are standardized by converting to uppercase and stripping excess spaces.
- Feature Engineering: New columns are created, such as total_repaid and debt_remaining.

```python
columns_to_clean = ['loan_number', 'region', 'country', 'loan_status']

            for col in columns_to_clean:
                df_silver[col] = df_silver[col].str.replace(r'[\$,]+', '', regex=True) 
                df_silver[col] = df_silver[col].str.replace(r'\s+', ' ', regex=True) 
                df_silver[col] = df_silver[col].str.replace("'", "") 
                df_silver[col] = df_silver[col].str.strip()
                df_silver[col] = df_silver[col].str.upper()
```

- The cleaned and transformed data is saved in Azure Blob Storage as a Silver version for further processing.

  ## Loading

  - The final step is loading the transformed data into the Azure SQL Database using a bulk insert operation.

  ```sql
  BULK INSERT dbo.WB_Loans
  FROM 'WB_Data_Loans__Silver.csv'
  WITH (
      DATA_SOURCE = 'WorldBankData',
      ROWTERMINATOR = '0x0a',
      FIELDTERMINATOR = ',',
      FIRSTROW = 2
  );
  ```

- Once the data is loaded into the database, additional queries are run to verify data integrity and perform analyses on the dataset.

  ### Code Highlights

  ** The Airflow DAG orchestrates the following tasks:
- **Data Extraction:** Fetches the World Bank data from the API and stores it in Azure Blob Storage as a CSV file.
- **Data Transformation:** Cleans and transforms the raw data, preparing it for analysis.
- **Data Loading:** Loads the transformed data into Azure SQL Database.
- **Analysis Tasks:** Performs queries on the Azure SQL Database to analyze loan amounts by region and country.

  ### Sample Analysis:

  - Regions with Highest Loan Debt:

 ```sql
SELECT region, ROUND(SUM(debt_remaining), 2) AS debt_remaining 
FROM dbo.WB_Loans 
GROUP BY region 
ORDER BY debt_remaining DESC;
```

- Countries with Highest Number of Active Loans:
  ```sql
  SELECT TOP 10 country, COUNT(DISTINCT loan_number) AS count_of_loans 
  FROM dbo.WB_Loans 
  WHERE debt_remaining > 0 AND loan_status <> 'Fully Paid'
  GROUP BY country 
  ORDER BY count_of_loans DESC;
  ```


  
#### You can copy this directly into your GitHub repository `README.md` or wherever you need to place the raw text.





