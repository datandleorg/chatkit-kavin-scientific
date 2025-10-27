// MongoDB initialization script
db = db.getSiblingDB('rag_db');

// Create a user for the application
db.createUser({
  user: 'rag_user',
  pwd: 'rag_password',
  roles: [
    {
      role: 'readWrite',
      db: 'rag_db'
    }
  ]
});

// Create collections with proper indexes
db.createCollection('documents');

// Create text index for full-text search
db.documents.createIndex({
  "text": "text",
  "filename": "text"
});

// Create compound index for document queries
db.documents.createIndex({
  "document_id": 1,
  "chunk_index": 1
});

// Create index for metadata filtering
db.documents.createIndex({
  "filename": 1,
  "created_at": -1
});

print('MongoDB initialization completed successfully!');
