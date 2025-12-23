import time
from common import tm, load_data, parse_yaml_structure, WORKSPACE_ID

def main():
    data = load_data()
    if not data: return
    parsed = parse_yaml_structure(data)
    
    print("--- Step 2: Creating Entities (Skeleton) ---")
    
    # common.py で定義された順序 (parsed['order']) に従って作成
    # 順序: Site -> Building -> Level -> Space -> EquipmentExt -> PointExt
    for category in parsed['order']:
        eids = parsed['hierarchy'].get(category, [])
        if not eids: continue
        print(f"\nProcessing category: {category} ({len(eids)} items)")
        
        for eid in eids:
            entity = parsed['entities'][eid]
            parent = entity['parent_id']
            
            # 親IDが存在しない(解析結果に含まれない)場合、$ROOTにする安全策
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
                print(f"  [Error] Failed to create {eid}: {e}")
            
            # APIレートリミット対策の微小ウェイト
            time.sleep(0.05)

if __name__ == "__main__":
    main()