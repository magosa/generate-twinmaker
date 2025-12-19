import time
from common import tm, load_data, parse_yaml_structure, WORKSPACE_ID

def main():
    data = load_data()
    if not data: return
    parsed = parse_yaml_structure(data)
    
    print("--- Step 0: Resetting All Resources ---")
    
    # 1. Entityの削除
    # 親子関係があるため、子から順に消す必要があります。
    # hierarchy_orderの逆順（Equipment -> Space -> ... -> Site）で処理します
    reverse_order = parsed['order'][::-1]
    
    print("\n[1/2] Deleting Entities...")
    for category in reverse_order:
        eids = parsed['hierarchy'].get(category, [])
        if not eids: continue
        
        for eid in eids:
            try:
                tm.delete_entity(
                    workspaceId=WORKSPACE_ID,
                    entityId=eid,
                    isRecursive=True # 子要素も強制的に削除
                )
                print(f"  [Deleted] Entity: {eid}")
            except tm.exceptions.ResourceNotFoundException:
                print(f"  [Skip] Entity not found: {eid}")
            except Exception as e:
                print(f"  [Error] Failed to delete entity {eid}: {e}")
            
            time.sleep(0.05)

    # 2. Component Typeの削除
    # Entityが消えた後でないと削除できません
    print("\n[2/2] Deleting Component Types...")
    
    # 設備系
    for type_id in parsed['equipment_types']:
        _delete_type(type_id)
        
    # 空間系
    spatial_types = ['Site', 'Building', 'Level', 'Space']
    for st in spatial_types:
        _delete_type(st)

    print("\nReset completed. You can now run 01_create_types.py")

def _delete_type(type_id):
    try:
        tm.delete_component_type(
            workspaceId=WORKSPACE_ID,
            componentTypeId=type_id
        )
        print(f"  [Deleted] Type: {type_id}")
    except tm.exceptions.ResourceNotFoundException:
        print(f"  [Skip] Type not found: {type_id}")
    except Exception as e:
        print(f"  [Error] Failed to delete type {type_id}: {e}")

if __name__ == "__main__":
    main()