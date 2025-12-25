import uuid
import time
from botocore.exceptions import ClientError
from common import WORKSPACE_ID, tm

# ==========================================
# 設定項目 (ここを変更して使用します)
# ==========================================

# 1. 更新対象
TARGET_COMPONENT_TYPE_ID = 'Site'   # 対象のコンポーネントタイプID
TARGET_PROPERTY_NAME     = 'id'     # 更新するプロパティ名

# 2. 更新モード ('UUID', 'FIXED', 'SEQUENCE')
UPDATE_MODE = 'UUID'

# 3. モード別パラメータ
FIXED_VALUE     = 'Active'
SEQUENCE_PREFIX = 'PT-'
SEQUENCE_START  = 1

# 4. 安全設定
DRY_RUN = True  # Trueの場合、実際の更新は行わずログ出力のみ行います

# ==========================================

def get_update_value(mode, index, current_val=None):
    """設定されたモードに基づいて更新後の値を生成する"""
    if mode == 'UUID':
        return str(uuid.uuid4())
    elif mode == 'FIXED':
        return FIXED_VALUE
    elif mode == 'SEQUENCE':
        return f"{SEQUENCE_PREFIX}{SEQUENCE_START + index:03d}"
    else:
        return None

def get_typed_value_map(value):
    """値をTwinMakerの型形式に変換"""
    if isinstance(value, bool):
        return {'booleanValue': value}
    elif isinstance(value, int):
        return {'integerValue': value}
    elif isinstance(value, float):
        return {'doubleValue': value}
    else:
        return {'stringValue': str(value)}

def main():
    print(f"--- Step 5: Batch Update Property ---")
    print(f"Workspace: {WORKSPACE_ID}")
    print(f"Target   : Type='{TARGET_COMPONENT_TYPE_ID}', Prop='{TARGET_PROPERTY_NAME}'")
    print(f"Mode     : {UPDATE_MODE}")
    if DRY_RUN:
        print("!!! DRY RUN MODE (No changes will be applied) !!!")

    update_count = 0
    error_count = 0
    
    try:
        print("\nStarting process...")
        
        # Paginatorの代わりにnextTokenを使った手動ページネーション
        next_token = None
        
        while True:
            # APIパラメータの準備
            list_params = {
                'workspaceId': WORKSPACE_ID,
                'filters': [{'componentTypeId': TARGET_COMPONENT_TYPE_ID}],
                'maxResults': 50  # 1回の取得件数
            }
            if next_token:
                list_params['nextToken'] = next_token

            # エンティティ一覧取得
            response = tm.list_entities(**list_params)
            
            # 取得したエンティティの処理
            for entity_summary in response.get('entitySummaries', []):
                entity_id = entity_summary['entityId']
                entity_name = entity_summary['entityName']
                
                try:
                    # エンティティ詳細取得
                    entity_detail = tm.get_entity(
                        workspaceId=WORKSPACE_ID,
                        entityId=entity_id
                    )
                    
                    components = entity_detail.get('components', {})
                    component_updates = {}

                    # コンポーネント走査
                    for comp_name, comp_data in components.items():
                        if comp_data.get('componentTypeId') == TARGET_COMPONENT_TYPE_ID:
                            
                            # 新しい値を生成
                            new_value = get_update_value(UPDATE_MODE, update_count)
                            
                            # 更新リクエスト作成
                            component_updates[comp_name] = {
                                'updateType': 'UPDATE',
                                'propertyUpdates': {
                                    TARGET_PROPERTY_NAME: {
                                        'value': get_typed_value_map(new_value)
                                    }
                                }
                            }

                    # 更新実行判定
                    if component_updates:
                        comps_str = ", ".join(component_updates.keys())
                        
                        if DRY_RUN:
                            # 予行演習ログ
                            print(f"  [DryRun] Would update '{entity_name}' ({entity_id}) | {comps_str}.{TARGET_PROPERTY_NAME} -> '{new_value}'")
                        else:
                            # 実更新
                            tm.update_entity(
                                workspaceId=WORKSPACE_ID,
                                entityId=entity_id,
                                componentUpdates=component_updates
                            )
                            print(f"  [OK] Updated '{entity_name}' ({entity_id}) | {comps_str}.{TARGET_PROPERTY_NAME} -> '{new_value}'")
                        
                        update_count += 1
                    
                    # APIレートリミット対策
                    time.sleep(0.05)

                except ClientError as e:
                    print(f"  [Error] Failed to process entity '{entity_id}': {e}")
                    error_count += 1

            # 次のページがあるか確認
            next_token = response.get('nextToken')
            if not next_token:
                break

    except Exception as e:
        print(f"[Fatal Error] Script execution failed: {e}")
        return

    print("-" * 30)
    print(f"Processing Complete.")
    print(f"  Processed: {update_count}")
    print(f"  Errors   : {error_count}")
    if DRY_RUN:
        print("\nTo apply changes, set DRY_RUN = False in the script.")

if __name__ == "__main__":
    main()