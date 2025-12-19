import time
from common import tm, load_data, parse_yaml_structure, WORKSPACE_ID

def main():
    data = load_data()
    if not data: return
    parsed = parse_yaml_structure(data)
    
    print("--- Step 2: Creating Entities (Skeleton) ---")
    
    # 作成順序
    order = ['Site', 'Building', 'Level', 'Space', 'EquipmentExt']
    
    for category in order:
        eids = parsed['hierarchy'].get(category, [])
        print(f"\nProcessing {category} ({len(eids)} items)...")
        
        for eid in eids:
            entity = parsed['entities'][eid]
            parent = entity['parent_id']
            
            # 親の存在チェックを緩和（ルート扱いにするなど）
            if parent != '$ROOT' and parent not in parsed['entities']:
                 parent = '$ROOT'

            try:
                tm.create_entity(
                    workspaceId=WORKSPACE_ID,
                    entityId=eid,
                    entityName=entity['name'],
                    parentEntityId=parent
                )
                print(f"  [OK] Created: {eid}")
            except tm.exceptions.ConflictException:
                print(f"  [Skip] Exists: {eid}")
            except Exception as e:
                print(f"  [Error] {eid}: {e}")
            
            # API制限対策
            time.sleep(0.05)

if __name__ == "__main__":
    main()