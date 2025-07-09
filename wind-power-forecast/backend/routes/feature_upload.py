import pandas as pd
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
import io
from datetime import datetime
import logging # Import logging

from sqlalchemy import text # Import text for raw SQL if needed (optional)
from db_session import db_session
from db_models import TrainPreMiddle, TrainPreShort # Import the new models
from services.file_service import allowed_file # Reuse existing file validation if desired

feature_upload_bp = Blueprint('feature_upload', __name__)

# Map table names to model classes
TABLE_MODEL_MAP = {
    'train_pre_middle': TrainPreMiddle,
    'train_pre_short': TrainPreShort
}

# Define a chunk size for processing large files
CHUNK_SIZE = 2000 # Process 1000 rows at a time, adjust as needed

def map_csv_to_model(row_dict, model_class):
    """Maps a dictionary (from CSV row) to the SQLAlchemy model attributes."""
    mapped_data = {}
    # Direct mapping for standard columns (case-insensitive matching for Timestamp)
    timestamp_val = None
    for key, value in row_dict.items():
        if key.lower() == 'timestamp':
            try:
                # Attempt to parse various timestamp formats
                timestamp_val = pd.to_datetime(value)
                mapped_data['Timestamp'] = timestamp_val
            except Exception as e:
                # Log warning but allow returning the original problematic value for error reporting
                current_app.logger.warning(f"Could not parse timestamp '{value}': {e}")
                mapped_data['Timestamp'] = None # Mark as None if parsing failed
                return mapped_data # Return immediately as timestamp is crucial
            break # Found timestamp, move on
            
    if mapped_data.get('Timestamp') is None:
         # If timestamp parsing failed or column not found
         return mapped_data # Return with Timestamp as None or missing

    # Mapping for feature columns (needs to match the structure in features.py)
    # Assumes CSV headers are like "100u_23.8_103.2"
    for csv_col_name, value in row_dict.items():
        # Skip timestamp and potential record_id in csv
        if csv_col_name.lower() != 'timestamp' and csv_col_name != 'record_id':
             # Construct the expected Python attribute name
            py_attr_name = f"col_{csv_col_name.replace('.', '_')}" 
            
            # Check if the model class actually has this attribute
            if hasattr(model_class, py_attr_name):
                 try:
                     # Convert to float, handle potential None/empty strings
                     mapped_data[py_attr_name] = float(value) if value not in [None, ''] else None
                 except (ValueError, TypeError) as e:
                     # Log warning but allow returning None for this feature
                     current_app.logger.warning(f"Could not convert feature '{csv_col_name}' value '{value}' to float for timestamp {timestamp_val}: {e}")
                     mapped_data[py_attr_name] = None

    return mapped_data


@feature_upload_bp.route('/api/upload_feature_csv', methods=['POST'])
def upload_feature_csv():
    """
    Handles CSV file upload, processing in chunks and performing bulk upserts.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    table_name = request.form.get('table_name')

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if not table_name or table_name not in TABLE_MODEL_MAP:
        return jsonify({"error": f"Invalid or missing 'table_name'. Must be one of: {list(TABLE_MODEL_MAP.keys())}"}), 400

    if not file.filename.lower().endswith('.csv'):
         return jsonify({"error": "Invalid file type. Only CSV allowed."}), 400

    TargetModel = TABLE_MODEL_MAP[table_name]
    
    total_inserted_count = 0
    total_updated_count = 0
    total_error_count = 0
    all_errors = []
    processed_chunks = 0

    try:
        # Use file.stream directly with pd.read_csv and chunksize
        # Wrap stream in io.TextIOWrapper if needed for encoding issues, e.g., io.TextIOWrapper(file.stream, encoding='utf-8')
        # Assuming default utf-8 or pandas handles it.
        chunk_iterator = pd.read_csv(file.stream, chunksize=CHUNK_SIZE, iterator=True)
        first_chunk = True

        with db_session() as session:
            for chunk_df in chunk_iterator:
                processed_chunks += 1
                current_app.logger.info(f"Processing chunk {processed_chunks} for {table_name}...")

                # --- Basic validation for the first chunk ---
                if first_chunk:
                    if not any(col.lower() == 'timestamp' for col in chunk_df.columns):
                         return jsonify({"error": "CSV must contain a 'Timestamp' column."}), 400
                    first_chunk = False # Only check header once

                to_insert = []
                to_update_mappings = [] # Use mappings for potential bulk update later if needed
                update_candidates = {} # Store mapped data for rows needing update: {timestamp: mapped_data}
                chunk_timestamps_valid = []
                row_processing_errors = []

                # --- 1. Pre-process chunk: Map rows and identify valid timestamps ---
                for index, row in chunk_df.iterrows():
                    original_row_dict = row.to_dict()
                    global_row_index = (processed_chunks - 1) * CHUNK_SIZE + index + 1 # Calculate global row index for logging
                    
                    try:
                        model_data = map_csv_to_model(original_row_dict, TargetModel)
                        
                        # Validate timestamp after mapping
                        target_timestamp = model_data.get('Timestamp')
                        if target_timestamp is None or pd.isna(target_timestamp):
                             raise ValueError(f"Could not parse Timestamp or Timestamp missing.")
                        
                        # Filter to only valid model attributes before adding to lists
                        valid_model_keys = {k for k in model_data if hasattr(TargetModel, k)}
                        filtered_model_data = {k: model_data[k] for k in valid_model_keys}
                        
                        # Store timestamp and data for DB check
                        chunk_timestamps_valid.append(target_timestamp)
                        update_candidates[target_timestamp] = filtered_model_data # Store full data keyed by timestamp

                    except Exception as e:
                        total_error_count += 1
                        err_msg = f"Row {global_row_index}: Error mapping/validating row - {str(e)}"
                        all_errors.append(err_msg)
                        row_processing_errors.append(err_msg) # Track errors for this chunk specifically if needed
                        current_app.logger.error(f"Error processing row {global_row_index} for {table_name}: {e}")


                # --- 2. Check existing records in DB for valid timestamps in this chunk ---
                existing_records_dict = {}
                if chunk_timestamps_valid: # Only query if there are valid timestamps
                     try:
                         existing_records = session.query(TargetModel).filter(TargetModel.Timestamp.in_(chunk_timestamps_valid)).all()
                         existing_records_dict = {record.Timestamp: record for record in existing_records}
                         current_app.logger.info(f"Chunk {processed_chunks}: Found {len(existing_records_dict)} existing records for {len(chunk_timestamps_valid)} valid timestamps.")
                     except Exception as db_query_error:
                          current_app.logger.error(f"Chunk {processed_chunks}: Database query failed: {db_query_error}", exc_info=True)
                          # Decide how to handle: skip chunk, return error immediately?
                          # For now, log and continue, rows won't be marked as updates.
                          # Consider adding chunk error count here.

                # --- 3. Prepare bulk insert list and update existing ORM objects ---
                for timestamp, mapped_data in update_candidates.items():
                     # Find corresponding ORM object (if it exists and DB query succeeded)
                     existing_record = existing_records_dict.get(timestamp)

                     if existing_record:
                         # Update existing ORM object directly
                         try:
                             for key, value in mapped_data.items():
                                 # Don't try to set Timestamp again if it's the key
                                 if key != 'Timestamp':
                                     setattr(existing_record, key, value)
                             total_updated_count += 1
                         except Exception as update_attr_err:
                             # Handle potential errors setting attributes
                             total_error_count += 1
                             err_msg = f"Error updating attributes for existing record with timestamp {timestamp}: {update_attr_err}"
                             all_errors.append(err_msg)
                             current_app.logger.error(err_msg)
                             # Remove from being updated to avoid issues on commit? Or let commit fail?
                     else:
                         # If not existing, prepare for bulk insert
                         to_insert.append(mapped_data)

                # --- 4. Perform bulk insert for the chunk ---
                if to_insert:
                    try:
                        session.bulk_insert_mappings(TargetModel, to_insert)
                        total_inserted_count += len(to_insert)
                        current_app.logger.info(f"Chunk {processed_chunks}: Bulk inserted {len(to_insert)} new records.")
                    except Exception as bulk_insert_err:
                        total_error_count += len(to_insert) # Count all as errors if bulk fails
                        err_msg = f"Chunk {processed_chunks}: Bulk insert failed: {str(bulk_insert_err)}"
                        all_errors.append(err_msg)
                        current_app.logger.error(err_msg, exc_info=True)
                        session.rollback() # Rollback chunk on bulk insert failure
                        # Important: Decide whether to continue with next chunk or abort
                        # For robustness, might continue but log the failure.
                        # Or re-raise to abort entire upload: raise bulk_insert_err


            # --- 5. Final commit after processing all chunks ---
            current_app.logger.info(f"Finished processing all chunks for {table_name}. Total Inserted: {total_inserted_count}, Total Updated: {total_updated_count}, Total Errors: {total_error_count}")
            try:
                session.commit()
                current_app.logger.info(f"Final commit successful for {table_name}.")
                if total_error_count == 0:
                    return jsonify({
                        "message": f"Successfully processed CSV for {table_name}.",
                        "inserted_count": total_inserted_count,
                        "updated_count": total_updated_count
                    }), 200
                else:
                    return jsonify({
                        "warning": f"Processed CSV for {table_name} with {total_error_count} errors.",
                        "inserted_count": total_inserted_count,
                        "updated_count": total_updated_count,
                        "error_count": total_error_count,
                        "errors": all_errors[:50] # Limit returned errors
                    }), 207 # Multi-Status
            except Exception as commit_error:
                 current_app.logger.error(f"Final commit failed for {table_name}: {commit_error}", exc_info=True)
                 session.rollback()
                 # Even if commit fails, report counts and errors encountered during processing
                 return jsonify({
                     "error": f"Failed to commit changes after processing: {commit_error}",
                     "processed_inserted_count": total_inserted_count,
                     "processed_updated_count": total_updated_count,
                     "error_count": total_error_count,
                     "errors": all_errors[:50]
                 }), 500

    except pd.errors.EmptyDataError:
        return jsonify({"error": "CSV file is empty."}), 400
    except Exception as e:
        # Catch potential errors during chunk iteration setup or other unexpected issues
        current_app.logger.error(f"Failed to process CSV upload for {table_name}: {e}", exc_info=True)
        # Attempt to rollback if session was started
        try:
            if 'session' in locals() and session.is_active:
                session.rollback()
        except Exception as rb_err:
            current_app.logger.error(f"Rollback attempt failed after error: {rb_err}")
            
        return jsonify({"error": f"An unexpected error occurred during processing: {str(e)}"}), 500 