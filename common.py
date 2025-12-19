import yaml
import boto3
import re
import os
from dotenv import load_dotenv

# --- 設定読み込み ---
load_dotenv()
WORKSPACE_ID = os.getenv('TWINMAKER_WORKSPACE_ID', 'MySmartBuildingWorkspace')
REGION_NAME = os.getenv('AWS_DEFAULT_REGION', 'ap-northeast-1')
YAML_FILE = os.getenv('INPUT_FILE', 'input/buildingA.yaml')

# AWS Client
tm = boto3.client('iottwinmaker', region_name=REGION_NAME)

def load_data():
    """YAMLファイルを読み込む"""
    if not os.path.exists(YAML_FILE):
        print(f"Error: Input file not found: {YAML_FILE}")
        return None
    with open(YAML_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def sanitize_id(text):
    """IDをTwinMakerで使用可能な形式に変換"""
    s = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(text))
    s = re.sub(r'_+', '_', s)
    s = s.strip('_')
    return s

def parse_yaml_structure(data):
    """YAMLデータを解析して構造化データを返す"""
    raw_data = data.get('data', {})
    points_map = {}
    equipment_types = {}
    entities = {}
    # 処理順序定義
    hierarchy_order = ['Site', 'Building', 'Level', 'Space', 'EquipmentExt']
    hierarchy = {k: [] for k in hierarchy_order}

    # Points定義の読み込み
    if 'PointExt' in raw_data:
        for pid, pdata in raw_data['PointExt'].items():
            points_map[pid] = pdata

    # エンティティとタイプの解析
    for category, items in raw_data.items():
        if category == 'PointExt': continue
        if category not in hierarchy: continue # 定義外のカテゴリは無視

        for eid, edata in items.items():
            hierarchy[category].append(eid)
            
            # 親IDの特定
            parent_id = '$ROOT'
            if 'isPartOf' in edata:
                parent_id = edata['isPartOf']
            elif 'locatedIn' in edata:
                parent_id = edata['locatedIn']
            elif isinstance(edata.get('locatedIn'), list):
                parent_id = edata['locatedIn'][0]

            # Component Typeの特定
            comp_type_id = category
            if category == 'EquipmentExt':
                raw_type = edata.get('deviceType', 'GenericEquipment')
                comp_type_id = sanitize_id(raw_type)
                
                # 型定義の蓄積
                if comp_type_id not in equipment_types:
                    equipment_types[comp_type_id] = {'points': {}}
                
                # Point定義のマッピング
                if 'hasPoint' in edata:
                    points = edata['hasPoint']
                    if isinstance(points, str): points = [points]
                    for pid in points:
                        p_info = points_map.get(pid)
                        if p_info:
                            prop_name = sanitize_id(p_info.get('pointType', pid))
                            equipment_types[comp_type_id]['points'][prop_name] = p_info

            entities[eid] = {
                'name': edata.get('name', eid),
                'parent_id': parent_id,
                'component_type_id': comp_type_id,
                'category': category,
                'raw_data': edata
            }
            
    return {
        'equipment_types': equipment_types,
        'entities': entities,
        'hierarchy': hierarchy,
        'order': hierarchy_order
    }