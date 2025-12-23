import time
from common import tm, load_data, parse_yaml_structure, WORKSPACE_ID
from botocore.exceptions import ClientError

# 修正済みのコンポーネントタイプIDを記録し、何度も修復処理が走るのを防ぐ
fixed_component_types = set()

def main():
    data = load_data()
    if not data: return
    parsed = parse_yaml_structure(data)
    
    print("--- Step 3: Attaching Components (Auto-Fix Mode) ---")
    
    success_count = 0
    error_count = 0

    # 処理順序に従ってコンポーネントをアタッチ
    for category in parsed['order']:
        eids = parsed['hierarchy'].get(category, [])
        if not eids: continue
        print(f"\nAttaching components for {category} ({len(eids)} items)...")
        
        # 現在のカテゴリに対応するスキーマ定義を取得（修復時に使用）
        category_schema = {}
        if category not in ['EquipmentExt', 'PointExt']:
            category_schema = parsed['category_property_schema'].get(category, {})
        elif category == 'PointExt':
            category_schema = parsed['category_property_schema'].get('Point', {})
        
        for eid in eids:
            entity = parsed['entities'][eid]
            ct_id = entity['component_type_id']
            flat_props = entity['properties']
            
            # 設備の場合は個別にスキーマを取得
            current_schema = category_schema
            if category == 'EquipmentExt':
                current_schema = parsed['equipment_property_schema'].get(ct_id, {})

            # プロパティ値の変換 (TwinMaker形式へ)
            update_props = {}
            for k, v in flat_props.items():
                if isinstance(v, bool):
                    val = {'booleanValue': v}
                elif isinstance(v, (int, float)):
                    val = {'doubleValue': float(v)}
                else:
                    val = {'stringValue': str(v)}
                update_props[k] = {'value': val}

            # Pointの場合の追加ロジック (カテゴリ分類)
            if category == 'PointExt':
                spec = str(flat_props.get('pointSpecification', ''))
                pt_type = str(flat_props.get('pointType', ''))
                
                category_val = 'Status'
                if 'Alarm' in spec or 'alarm' in pt_type: category_val = 'Alarm'
                elif 'Command' in spec or 'switch' in pt_type: category_val = 'Command'
                elif 'Setpoint' in spec or 'setpoint' in pt_type: category_val = 'Setpoint'
                elif 'Measurement' in spec or 'sensor' in pt_type: category_val = 'Measurement'
                elif 'Metering' in spec or 'meter' in pt_type: category_val = 'Metering'
                
                update_props['category'] = {'value': {'stringValue': category_val}}
                if 'pointType' in flat_props:
                    update_props['point_type'] = {'value': {'stringValue': str(flat_props['pointType'])}}
                if 'unit' in flat_props:
                    update_props['unit'] = {'value': {'stringValue': str(flat_props['unit'])}}

            # コンポーネントのアタッチ実行（スキーマ情報も渡す）
            if attach_component_safely(eid, ct_id, update_props, current_schema):
                success_count += 1
            else:
                error_count += 1
            
            time.sleep(0.05) 

    print(f"\nCompleted. OK: {success_count}, Error: {error_count}")

def attach_component_safely(entity_id, component_type_id, properties, schema_def):
    """
    コンポーネントを作成し、Abstract型エラーが出た場合は自動修復してリトライする
    """
    component_name = 'main'
    
    # 実行用ヘルパー関数
    def execute_update(update_type):
        tm.update_entity(
            workspaceId=WORKSPACE_ID,
            entityId=entity_id,
            componentUpdates={
                component_name: {
                    'componentTypeId': component_type_id,
                    'updateType': update_type,
                    'propertyUpdates': properties
                }
            }
        )

    try:
        # 1. まずCREATE (新規作成) を試す
        execute_update('CREATE')
        print(f"  [OK] Created component for: {entity_id}")
        return True

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']

        # パターンA: 既にコンポーネントが存在する -> UPDATE (更新) でリトライ
        if error_code == 'ValidationException' and 'exist' in error_msg:
            try:
                execute_update('UPDATE')
                print(f"  [OK] Updated component for: {entity_id}")
                return True
            except Exception as update_err:
                print(f"  [Error] Update failed for {entity_id}: {update_err}")
                return False

        # パターンB: 型が抽象(Abstract)である -> 型を自動修復してリトライ
        elif error_code == 'ValidationException' and 'Abstract ComponentType' in error_msg:
            # まだ修復していない型なら修復を試みる
            if component_type_id not in fixed_component_types:
                print(f"  [Auto-Fix] Detected abstract type '{component_type_id}'. Repairing...")
                
                if fix_abstract_component_type(component_type_id, schema_def):
                    fixed_component_types.add(component_type_id)
                    # 修復後に再度CREATEを試行
                    try:
                        execute_update('CREATE')
                        print(f"  [OK] Created component for: {entity_id} (after fix)")
                        return True
                    except Exception as retry_err:
                        print(f"  [Error] Retry failed for {entity_id} after fix: {retry_err}")
                        return False
                else:
                    print(f"  [Error] Failed to repair type '{component_type_id}'.")
                    return False
            else:
                # 既に修復を試みたはずなのにエラーが出る場合
                print(f"  [Error] Type '{component_type_id}' is still invalid despite repair attempt.")
                return False

        else:
            # その他のエラー
            print(f"  [Error] Create failed for {entity_id}: {e}")
            return False

    except Exception as e:
        print(f"  [Error] Unexpected error for {entity_id}: {e}")
        return False

def fix_abstract_component_type(type_id, schema_def):
    """
    問題のあるComponent Typeを削除し、正しい設定(Static/Concrete)で再作成する
    """
    try:
        # 1. 削除
        try:
            tm.delete_component_type(workspaceId=WORKSPACE_ID, componentTypeId=type_id)
            print(f"    - Deleted invalid type: {type_id}")
            time.sleep(1) # 反映待ち
        except tm.exceptions.ResourceNotFoundException:
            pass 
        except Exception as e:
            print(f"    - Failed to delete type: {e}")
            return False

        # 2. プロパティ定義の構築 (全て静的データとして定義)
        prop_defs = {}
        for prop_name, data_type in schema_def.items():
            prop_defs[prop_name] = {
                'dataType': {'type': data_type},
                'isTimeSeries': False,       # False固定
                'isStoredExternally': False, # False固定
                'isExternalId': False
            }

        # 3. 再作成 (isSingleton=False を明示)
        tm.create_component_type(
            workspaceId=WORKSPACE_ID,
            componentTypeId=type_id,
            propertyDefinitions=prop_defs,
            isSingleton=False  # これが重要
        )
        print(f"    - Re-created concrete type: {type_id}")
        return True

    except Exception as e:
        print(f"    - Critical error during repair: {e}")
        return False

if __name__ == "__main__":
    main()