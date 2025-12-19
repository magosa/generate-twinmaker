import time
from common import tm, load_data, parse_yaml_structure, WORKSPACE_ID
from botocore.exceptions import ClientError

def main():
    data = load_data()
    if not data: return
    parsed = parse_yaml_structure(data)
    
    print("--- Step 3: Attaching Components (Retry Mode) ---")
    
    success_count = 0
    error_count = 0

    # 処理順序
    for category in parsed['order']:
        eids = parsed['hierarchy'].get(category, [])
        if not eids: continue
        print(f"\nAttaching components for {category} ({len(eids)} items)...")
        
        for eid in eids:
            entity = parsed['entities'][eid]
            ct_id = entity['component_type_id']
            
            # プロパティ値の準備
            props = {}
            props['name'] = {'value': {'stringValue': str(entity['name'])}}
            
            raw = entity['raw_data']
            if 'identifiers' in raw:
                for ident in raw['identifiers']:
                    if ident['key'] == 'asset_tag':
                        props['asset_tag'] = {'value': {'stringValue': str(ident['value'])}}

            # コンポーネントのアタッチ（作成 または 更新）
            if attach_component_safely(eid, ct_id, props):
                success_count += 1
            else:
                error_count += 1
            
            time.sleep(0.1)

    print(f"\nCompleted. OK: {success_count}, Error: {error_count}")

def attach_component_safely(entity_id, component_type_id, properties):
    """CREATEを試行し、失敗したらUPDATEを試行する"""
    component_name = 'main' # コンポーネント名を固定

    # 1. まず CREATE (新規作成) を試す
    try:
        tm.update_entity(
            workspaceId=WORKSPACE_ID,
            entityId=entity_id,
            componentUpdates={
                component_name: {
                    'componentTypeId': component_type_id,
                    'updateType': 'CREATE',  # まずは作成！
                    'propertyUpdates': properties
                }
            }
        )
        print(f"  [OK] Created component for: {entity_id}")
        return True

    except ClientError as e:
        # エラーコードを確認
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']

        # 「既に存在する」系のエラーなら UPDATE に切り替え
        # ValidationExceptionで "already exists" が含まれる場合などを想定
        if error_code == 'ValidationException' and 'exist' in error_msg:
            try:
                # 2. 存在する場合は UPDATE (更新) を試す
                tm.update_entity(
                    workspaceId=WORKSPACE_ID,
                    entityId=entity_id,
                    componentUpdates={
                        component_name: {
                            'componentTypeId': component_type_id,
                            'updateType': 'UPDATE',  # 更新モード
                            'propertyUpdates': properties
                        }
                    }
                )
                print(f"  [OK] Updated component for: {entity_id}")
                return True
            except Exception as update_err:
                print(f"  [Error] Update failed for {entity_id}: {update_err}")
                return False
        else:
            # その他のエラー（そもそも親Entityがない、型定義がおかしい等）
            print(f"  [Error] Create failed for {entity_id}: {e}")
            return False
    except Exception as e:
        print(f"  [Error] Unexpected error for {entity_id}: {e}")
        return False

if __name__ == "__main__":
    main()