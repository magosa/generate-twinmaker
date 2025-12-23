from common import tm, load_data, parse_yaml_structure, WORKSPACE_ID

def main():
    data = load_data()
    if not data: return
    parsed = parse_yaml_structure(data)
    
    print("--- Step 1: Creating Component Types ---")

    # 1. 空間系 + Point型
    # (Site, Building, Level, Space, Point)
    for type_id, schema_defs in parsed['category_property_schema'].items():
        # 定義が空でも Point は必ず作成する (プロパティがない場合でも型自体は必要)
        if not schema_defs and type_id != 'Point': continue
        
        print(f"Defining Type: {type_id} (Props: {len(schema_defs)})")
        
        prop_defs = {}
        for prop_name, data_type in schema_defs.items():
            prop_defs[prop_name] = {
                'dataType': {'type': data_type},
                'isTimeSeries': False,       # エラー回避のためFalse固定
                'isStoredExternally': False, # エラー回避のためFalse固定
                'isExternalId': False
            }
            
        _create_type(type_id, prop_defs, is_singleton=False)

    # 2. 設備系型 (pac_*, sensor_*, lighting_*)
    for type_id, schema_defs in parsed['equipment_property_schema'].items():
        print(f"Defining Equipment: {type_id} (Props: {len(schema_defs)})")
        
        prop_defs = {}
        for prop_name, data_type in schema_defs.items():
            prop_defs[prop_name] = {
                'dataType': {'type': data_type},
                'isTimeSeries': False,       # 設備プロパティは基本Static
                'isStoredExternally': False,
                'isExternalId': False
            }
        
        # is_singleton=False を指定して「具体的(Concrete)」な型として作成
        _create_type(type_id, prop_defs, is_singleton=False)

def _create_type(type_id, props, is_singleton=False):
    """ComponentTypeを作成または更新する"""
    try:
        tm.create_component_type(
            workspaceId=WORKSPACE_ID,
            componentTypeId=type_id,
            propertyDefinitions=props,
            isSingleton=is_singleton
        )
        print(f"  [OK] Created: {type_id}")
    except tm.exceptions.ConflictException:
        try:
            # 既に存在する場合は設定を更新（プロパティ追加など）
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