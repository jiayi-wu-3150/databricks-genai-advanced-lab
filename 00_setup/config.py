# Databricks notebook source
# MAGIC %md
# MAGIC ## Load configuration file
# MAGIC
# MAGIC Please change your catalog and schema here to run the demo in a different schema.

# COMMAND ----------

catalog_name = "uc_fd_genai"
schema_name = "jywu"
VECTOR_SEARCH_ENDPOINT_NAME="shared_workshop_endpoint"
EXPERIMENT_NAME = "/Shared/genai-advanced-workshop"

# COMMAND ----------

print(f"import catalog_name as {catalog_name}")
print(f"import schema_name as {schema_name}")
print(f"We will use VECTOR_SEARCH_ENDPOINT_NAME as {VECTOR_SEARCH_ENDPOINT_NAME}")
print(f"We will use experiment_name as {EXPERIMENT_NAME}")