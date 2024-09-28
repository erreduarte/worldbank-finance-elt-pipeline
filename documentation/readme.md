## Proof of Successful Pipeline Execution

### Airflow DAG and Task Success
Below are screenshot details of the Airflow UI showing a successful DAG run for this pipeline:
<br>
<br>

##### -**DAG GENERAL VIEW:**
  
 1 -  General Details
 ![DAG Success](.screen-shots/dag_run_details.JPG) <br>
 
 2 - Graph Run VIew  
 ![DAG_Graph_Tree](.screen-shots/dag_run_graph_tree.png)

- **Tasks Logs**

Below are log details for each of the Airflow successful tasks run for this pipeline:

- TASK 1: Fetch Data 
![Fetch Data](.logs/1_fetch_WB_data.log) <br>

- TASK 2: Transform Data
![Transform Data](.logs/2_transform_wb_data.log) <br>

- TASK 3: Create Table in Azure SQL Database 
![Create Table](.logs/3_create_MS_table.log) <br>

- TASK 4: Populate newly created table
![Populate Table](.logs/4_populate_dbo_WB_Loans.log) <br>

- TASK 5: Analyze regions with the highest loan debts
![Analysis 1](.logs/5_analysis_regions.log) <br>

- TASK 6: Analyze countries with highest loan debts per region
![Analysis 2](.logs/6_analysis_countries.log) <br>

- TASK 7: Analyze countries with highest number of active loans
![Analysis 3](.logs/7_analysis_loans.log)




