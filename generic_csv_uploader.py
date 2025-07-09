import requests
import argparse
import os
import json # Untuk pretty print respons JSON

def upload_csv_to_endpoint(csv_file_path, full_api_url, additional_form_data=None):
    """
    Uploads a CSV file to the specified full API endpoint URL.

    Args:
        csv_file_path (str): Path to the CSV file.
        full_api_url (str): The complete URL of the API endpoint
                            (e.g., 'http://localhost:5000/api/upload_feature_csv'
                            or 'http://localhost:5000/actual_power/batch').
        additional_form_data (dict, optional): A dictionary of additional key-value
                                               pairs to send as form data.
                                               Defaults to None.
    """
    if not os.path.exists(csv_file_path):
        print(f"Error: File not found at {csv_file_path}")
        return False
    if not os.path.isfile(csv_file_path):
        print(f"Error: Path {csv_file_path} is not a file.")
        return False
    if not csv_file_path.lower().endswith('.csv'):
        print(f"Error: File {csv_file_path} is not a CSV file.")
        return False

    # Nama file yang akan dikirim dalam request
    file_name_for_request = os.path.basename(csv_file_path)

    # Siapkan payload file
    files_to_upload = {'file': (file_name_for_request, None, 'text/csv')} # File object akan diisi di dalam 'with open'

    # Siapkan data form tambahan jika ada
    form_data_payload = additional_form_data if additional_form_data else {}

    try:
        with open(csv_file_path, 'rb') as f:
            files_to_upload['file'] = (file_name_for_request, f, 'text/csv') # Isi file object sekarang

            print(f"Uploading '{csv_file_path}' to '{full_api_url}'...")
            if form_data_payload:
                print(f"With additional form data: {form_data_payload}")

            # Mengatur timeout yang wajar, sesuaikan jika perlu
            response = requests.post(full_api_url, files=files_to_upload, data=form_data_payload, timeout=600) # Timeout 10 menit

            print(f"\nResponse Status Code: {response.status_code}")
            try:
                response_data = response.json()
                print("Response JSON:")
                print(json.dumps(response_data, indent=2)) # Pretty print
            except requests.exceptions.JSONDecodeError:
                print("Response Text (not JSON):")
                print(response.text)

            if 200 <= response.status_code < 300:
                print("\nUpload successful (or partially successful if status is 207).")
                return True
            else:
                print("\nUpload failed or encountered errors.")
                return False

    except requests.exceptions.ConnectionError as e:
        print(f"Error: Could not connect to the server at {full_api_url}.")
        print(f"Details: {e}")
        print("Please ensure your Flask application is running and accessible.")
    except requests.exceptions.Timeout:
        print(f"Error: The request to {full_api_url} timed out.")
        print("The file might be too large or the server is taking too long to process.")
    except FileNotFoundError: # Seharusnya sudah ditangani di awal, tapi sebagai jaring pengaman
        print(f"Error: The file '{csv_file_path}' was not found during open.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload a CSV file to a specified API endpoint.")
    parser.add_argument("csv_file", help="Path to the CSV file to upload.")
    parser.add_argument("api_url", help="The full URL of the API endpoint for CSV upload.")
    parser.add_argument("--form-data", nargs='*',
                        help="Additional form data as key=value pairs. Example: table_name=train_pre_middle another_key=value2")

    args = parser.parse_args()

    # Memproses --form-data
    additional_data = {}
    if args.form_data:
        for item in args.form_data:
            if '=' in item:
                key, value = item.split('=', 1)
                additional_data[key] = value
            else:
                print(f"Warning: Skipping invalid form data item '{item}'. Expected format: key=value")

    upload_csv_to_endpoint(args.csv_file, args.api_url, additional_data)