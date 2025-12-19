from common import tm, load_data, parse_yaml_structure, WORKSPACE_ID

def main():
    data = load_data()
    if not data: return
    parsed = parse_yaml_structure(data)
    
    print("--- Step 1: Creating Component Types (Static Mode) ---")

    # 1. 空間系の型を作成
    spatial_types = ['Site', 'Building', 'Level', 'Space']
    for st in spatial_types:
        _create_type(st, {
            'name': {'dataType': {'type': 'STRING'}},
            'description': {'dataType': {'type': 'STRING'}}
        })

    # 2. 設備系の型を作成
    for type_id, schema in parsed['equipment_types'].items():
        prop_defs = {
            'name': {'dataType': {'type': 'STRING'}},
            'asset_tag': {'dataType': {'type': 'STRING'}}
        }
        
        # ポイント定義からプロパティを作成
        for pt_name, pt_data in schema['points'].items():
            dtype = {'type': 'STRING'}
            spec = pt_data.get('pointSpecification', '')
            # 数値型かどうかの簡易判定
            if spec in ['Measurement', 'Setpoint'] or 'temp' in pt_name or 'humidity' in pt_name:
                dtype = {'type': 'DOUBLE'}
            
            # 【重要】まずは静的データとして作成（エラー回避）
            prop_defs[pt_name] = {
                'dataType': dtype,
                'isTimeSeries': False,       # True -> False
                'isStoredExternally': False, # True -> False
                'isExternalId': False
            }
        
        # デバッグ: プロパティ数の確認
        print(f"Defining Type: {type_id} (Props: {len(prop_defs)})")
        
        # 明示的に isSingleton=False を指定
        _create_type(type_id, prop_defs, is_singleton=False)

def _create_type(type_id, props, is_singleton=False):
    try:
        tm.create_component_type(
            workspaceId=WORKSPACE_ID,
            componentTypeId=type_id,
            propertyDefinitions=props,
            isSingleton=is_singleton
        )
        print(f"  [OK] Created: {type_id}")
    except tm.exceptions.ConflictException:
        # 既存の場合はアップデートを試みる（プロパティ変更を反映するため）
        try:
            tm.update_component_type(
                workspaceId=WORKSPACE_ID,
                componentTypeId=type_id,
                propertyDefinitions=props,
                isSingleton=is_singleton
            )
            print(f"  [OK] Updated: {type_id}")
        except Exception as e:
            print(f"  [Error] Update failed for {type_id}: {e}")
    except Exception as e:
        print(f"  [Error] Create failed for {type_id}: {e}")

if __name__ == "__main__":
    main()