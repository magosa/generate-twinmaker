import csv
import time
import os
import boto3
from dotenv import load_dotenv
from common import WORKSPACE_ID, REGION_NAME, CSV_FILE_PATH


# AWS Client (common.pyと同様の設定を使用)
tm = boto3.client('iottwinmaker', region_name=REGION_NAME)

def main():
    print(f"--- Step 4: Updating Point IDs from CSV ---")
    print(f"Reading CSV: {CSV_FILE_PATH}")

    if not os.path.exists(CSV_FILE_PATH):
        print(f"[Error] CSV file not found: {CSV_FILE_PATH}")
        return

    success_count = 0
    error_count = 0
    skip_count = 0

    try:
        # utf-8-sig を指定することでBOM付きCSVも正しく読み込めます
        with open(CSV_FILE_PATH, mode='r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            
            # カラム名の確認
            if 'Point' not in reader.fieldnames or 'twinPointId' not in reader.fieldnames:
                print(f"[Error] CSV must contain 'Point' and 'twinPointId' columns.")
                print(f"Found columns: {reader.fieldnames}")
                return

            print("Starting update process...")

            for row in reader:
                entity_id = row.get('Point', '').strip()
                new_id_value = row.get('twinPointId', '').strip()

                if not entity_id or not new_id_value:
                    print(f"  [Skip] Invalid row data: {row}")
                    skip_count += 1
                    continue

                try:
                    # コンポーネントプロパティの更新
                    # 'main' コンポーネント (Type: Point) の 'id' プロパティを更新します
                    tm.update_entity(
                        workspaceId=WORKSPACE_ID,
                        entityId=entity_id,
                        componentUpdates={
                            'main': {
                                'componentTypeId': 'Point',
                                'updateType': 'UPDATE',
                                'propertyUpdates': {
                                    'id': {
                                        'value': {'stringValue': new_id_value}
                                    }
                                }
                            }
                        }
                    )
                    print(f"  [OK] Updated '{entity_id}' id -> {new_id_value}")
                    success_count += 1

                except tm.exceptions.ResourceNotFoundException:
                    print(f"  [Error] Entity not found: {entity_id}")
                    error_count += 1
                except Exception as e:
                    print(f"  [Error] Failed to update '{entity_id}': {e}")
                    error_count += 1
                
                # APIレートリミット対策
                time.sleep(0.05)

    except Exception as e:
        print(f"[Fatal Error] Could not process CSV file: {e}")
        return

    print("-" * 30)
    print(f"Update Completed.")
    print(f"  Success: {success_count}")
    print(f"  Errors : {error_count}")
    print(f"  Skipped: {skip_count}")

if __name__ == "__main__":
    main()