# General data handling
import os
import pandas as pd
import numpy as np
import duckdb

# Sentence Transformers
from sentence_transformers import SentenceTransformer

# Other helpers
from tqdm import tqdm

# Connect to DuckDB database
db = duckdb.connect(database='patents_training.db')

# Define path to save embeddings
checkpoint_path = 'patentsberta_embeddings_checkpoint.npy'
start_idx = 0

# Convert raw data to pandas dataframe
data = db.sql("SELECT * FROM patents_raw").df()

# 
data = data[~data['abstract'].isna()]

# Concatenate title and abstract for input into sentence transformer
data = data.dropna(subset=['title', 'abstract']).reset_index(drop=True)
data['text'] = data['title'] + ' [SEP] ' + data['abstract']

# Load model
model = SentenceTransformer('AI-Growth-Lab/PatentSBERTa')

# Index for restart
if os.path.exists(checkpoint_path):
    embeddings = list(np.load(checkpoint_path, allow_pickle=True))
    start_idx = len(embeddings)
    print(f"Resuming from {start_idx}")
else:
    embeddings = []

batch_size = 64
texts = data['text'].tolist()[start_idx:]

# create embeddings
for i in range(0, len(texts), batch_size):
    batch = texts[i:i+batch_size]
    embeddings.extend(model.encode(batch, show_progress_bar=True))
    np.save(checkpoint_path, embeddings) 

print("Saving done!")

