# Databricks notebook source
# MAGIC %md
# MAGIC # Create an unstructured data pipeline for GenAI retrievers
# MAGIC
# MAGIC Before building vector search indexes, it's essential to first prepare your unstructured data through a dedicated data engineering step. This involves ingesting, cleaning, and transforming raw documents into a structured format—typically chunked, metadata-enriched, and stored in Delta tables. This foundation ensures your GenAI retrievers operate on high-quality, queryable content.

# COMMAND ----------

# MAGIC %run ../00_setup/config

# COMMAND ----------

query = f"""
SELECT path
FROM READ_FILES('/Volumes/{catalog_name}/{schema_name}/pdfs/', format => 'binaryFile')
LIMIT 2
"""

spark.sql(query).show(truncate=False)

# COMMAND ----------

dbutils.widgets.text("catalog_name", catalog_name)
dbutils.widgets.text("schema_name", schema_name)

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT path
# MAGIC FROM READ_FILES('/Volumes/' || :catalog_name || '/' || :schema_name || '/pdfs/', format => 'binaryFile')
# MAGIC LIMIT 2
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Extracting the information using `ai_parse_document`
# MAGIC Databricks provides a builtin `ai_parse_document` function, leveraging AI to analyze and extract PDF information as text. This makes it super easy to ingest unstructured information!
# MAGIC
# MAGIC - Easy to adopt. Recommended for the POC and long-term. 
# MAGIC - This AI function can work with PDF, JPG, and PNG. The product team recently added PPTX as well. 
# MAGIC
# MAGIC https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_parse_document?language=SQL

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT path FROM READ_FILES('/Volumes/databricks_workshop/jywu/pdfs/', format => 'binaryFile') LIMIT 2

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT ai_parse_document(content) AS parsed_document
# MAGIC FROM READ_FILES('/Volumes/databricks_workshop/jywu/pdfs/', format => 'binaryFile') LIMIT 2

# COMMAND ----------

# MAGIC %sql
# MAGIC WITH corpus AS (
# MAGIC   SELECT
# MAGIC     path,
# MAGIC     ai_parse_document(content) AS parsed
# MAGIC   FROM
# MAGIC     READ_FILES('/Volumes/databricks_workshop/jywu/pdfs/', format => 'binaryFile')
# MAGIC )
# MAGIC SELECT
# MAGIC   path,
# MAGIC   parsed:document:pages,
# MAGIC   parsed:document:elements,
# MAGIC   parsed:corrupted_data,
# MAGIC   parsed:error_status,
# MAGIC   parsed:metadata
# MAGIC FROM corpus;

# COMMAND ----------

# MAGIC %sql
# MAGIC # -- unflatten json
# MAGIC WITH corpus AS (
# MAGIC   SELECT
# MAGIC     path,
# MAGIC     ai_parse_document(content) AS parsed
# MAGIC   FROM READ_FILES('/Volumes/uc_fd_genai/jywu/pdfs/', format => 'binaryFile')
# MAGIC )
# MAGIC SELECT
# MAGIC   c.path                      AS doc_uri,
# MAGIC   e.col.bbox[0].page_id       AS page_id,
# MAGIC   e.col.content,
# MAGIC   e.col.description,
# MAGIC   e.col.type,
# MAGIC   e.col.bbox[0].coord[0]      AS x0,
# MAGIC   e.col.bbox[0].coord[1]      AS y0,
# MAGIC   e.col.bbox[0].coord[2]      AS x1,
# MAGIC   e.col.bbox[0].coord[3]      AS y1
# MAGIC FROM corpus c
# MAGIC LATERAL VIEW explode(
# MAGIC   from_json(
# MAGIC     variant_get(
# MAGIC       variant_get(c.parsed, '$.document', 'VARIANT'),
# MAGIC       '$.elements',
# MAGIC       'STRING'
# MAGIC     ),
# MAGIC     'ARRAY<STRUCT<
# MAGIC         page_id INT,
# MAGIC         content STRING,
# MAGIC         description STRING,
# MAGIC         type STRING,
# MAGIC         bbox ARRAY<STRUCT<
# MAGIC           page_id INT,
# MAGIC           coord ARRAY<DOUBLE>
# MAGIC         >>
# MAGIC     >>'
# MAGIC   )
# MAGIC ) e
# MAGIC LIMIT 20


# COMMAND ----------

# MAGIC %sql
# MAGIC # -- combine them together for chunking
# MAGIC WITH corpus AS (
# MAGIC   SELECT
# MAGIC     path,
# MAGIC     ai_parse_document(content) AS parsed
# MAGIC   FROM READ_FILES('/Volumes/uc_fd_genai/jywu/pdfs/', format => 'binaryFile')
# MAGIC )
# MAGIC SELECT
# MAGIC   path AS doc_uri,
# MAGIC   array_join(
# MAGIC     transform(
# MAGIC       filter(
# MAGIC         parsed:document:elements::ARRAY<STRUCT<content:STRING, description:STRING>>,
# MAGIC         e -> e.content IS NOT NULL OR e.description IS NOT NULL
# MAGIC       ),
# MAGIC       e -> coalesce(e.content, e.description)
# MAGIC     ),
# MAGIC     '\n'
# MAGIC   ) AS content
# MAGIC FROM corpus;


# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Python UDF
# MAGIC Databricks' notebook [template](https://docs.databricks.com/aws/en/notebooks/source/generative-ai/unstructured-data-pipeline.html) to parse, chunk and create index. PDF, DOCX, HTML, TXT, MD, JSON are included in the template and the logic can be extended.
# MAGIC - Recommended for quick trial and error as it requires additional code.
# MAGIC - This is a more hard-coded way but more robust as well. 
# MAGIC - Search for `file_parser` function to take a closer look.