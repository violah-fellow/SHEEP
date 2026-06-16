# General data handling
import os
import pandas as pd
import numpy as np
import duckdb
import torch

# Sentence Transformers
from transformers import AutoTokenizer
from adapters import AutoAdapterModel

# Other helpers
from tqdm import tqdm

# Connect to DuckDB database
db = duckdb.connect(database='publications.db')

# Define path to save embeddings
checkpoint_path = 'specter_embeddings_checkpoint.npy'
start_idx = 0

# Convert raw data to pandas dataframe
data = db.sql("SELECT * FROM publications_subset").df()

# Concatenate title and abstract for input into sentence transformer
data['text'] = data['title'] + ' [SEP] ' + data['abstract']

# Load base model and tokenizer
tokenizer = AutoTokenizer.from_pretrained('allenai/specter2_base')
model = AutoAdapterModel.from_pretrained('allenai/specter2_base')

# Load classification adapter
model.load_adapter("allenai/specter2_classification", 
                   source="hf", 
                   load_as="specter2_cls", 
                   set_active=True)
model.eval()

# Function to encode publications
def get_embeddings(texts, batch_size=32):
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        inputs = tokenizer(batch, padding=True, truncation=True,
                          max_length=512, return_tensors='pt')
        with torch.no_grad():
            outputs = model(**inputs)
        # CLS token as document embedding
        embeddings = outputs.last_hidden_state[:, 0, :]
        all_embeddings.append(embeddings.numpy())
        
    return np.vstack(all_embeddings)


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
    embeddings.extend(get_embeddings(batch))
    np.save(checkpoint_path, embeddings) 

print("Saving done!")

