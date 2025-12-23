import yaml
import boto3
import re
import os
from dotenv import load_dotenv

# --- 設定読み込み ---
load_dotenv()
WORKSPACE_ID = os.getenv('TWINMAKER_WORKSPACE_ID', 'MySmartBuildingWorkspace')
REGION_NAME = os.getenv('AWS_DEFAULT_REGION', 'ap-northeast-1')
YAML_FILE = os.getenv('INPUT_FILE', 'data/buildingA.yaml')

# AWS Client
tm = boto3.client('iottwinmaker', region_name=REGION_NAME)

def load_data():
    """YAMLファイルを読み込む"""
    if not os.path.exists(YAML_FILE):
        print(f"Error: Input file not found: {YAML_FILE}")
        return None
    with open(YAML_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def sanitize_key(text):
    """TwinMakerのキーとして使える形式に変換"""
    s = re.sub(r'[^a-zA-Z0-9_]', '_', str(text))
    s = re.sub(r'_+', '_', s)
    s = s.strip('_')
    if s and s[0].isdigit():
        s = 'prop_' + s
    return s

def get_twinmaker_type(value):
    """Pythonの型からTwinMakerのDataTypeを判定"""
    if isinstance(value, bool): return 'BOOLEAN'
    if isinstance(value, (int, float)): return 'DOUBLE'
    return 'STRING'

def flatten_properties(raw_data):
    """ネストされたYAMLデータをフラットな辞書に変換"""
    props = {}
    exclude_keys = [
        'identifiers', 'customTags', 'customProperties', 
        'hasPart', 'isPartOf', 'locatedIn', 'hasPoint', 
        'isLocationOf', 'isPointOf', 'pointType', 
        'pointSpecification', 'deviceType'
    ]
    
    for k, v in raw_data.items():
        if k not in exclude_keys and not isinstance(v, (dict, list)):
            props[sanitize_key(k)] = v

    if 'identifiers' in raw_data:
        for item in raw_data['identifiers']:
            props[sanitize_key(item['key'])] = item['value']

    if 'customTags' in raw_data:
        for item in raw_data['customTags']:
            props[sanitize_key(item['key'])] = item['flag']

    if 'customProperties' in raw_data:
        for group in raw_data['customProperties']:
            group_key = sanitize_key(group['key'])
            for entry in group['entries']:
                entry_key = sanitize_key(entry['key'])
                props[f"{group_key}_{entry_key}"] = entry['value']
    
    return props

def parse_yaml_structure(data):
    """YAMLデータを解析して構造化データを返す"""
    raw_data = data.get('data', {})
    
    equipment_types = {} 
    entities = {}
    
    # スキーマ定義用コンテナ
    category_property_schema = {
        'Site': {}, 'Building': {}, 'Level': {}, 'Space': {}, 'Point': {}
    }
    
    # 処理順序
    hierarchy_order = ['Site', 'Building', 'Level', 'Space', 'EquipmentExt', 'PointExt']
    hierarchy = {k: [] for k in hierarchy_order}

    # 親子関係マッピング
    point_parent_map = {}
    if 'EquipmentExt' in raw_data:
        for equip_id, equip_data in raw_data['EquipmentExt'].items():
            if 'hasPoint' in equip_data:
                points = equip_data['hasPoint']
                if isinstance(points, str): points = [points]
                for pid in points:
                    point_parent_map[pid] = equip_id

    # --- 解析ループ ---
    for category, items in raw_data.items():
        if category not in hierarchy: continue 

        for eid, edata in items.items():
            hierarchy[category].append(eid)
            
            # 親ID決定
            parent_id = '$ROOT'
            if category == 'PointExt':
                parent_id = point_parent_map.get(eid, '$ROOT')
            elif 'isPartOf' in edata:
                parent_id = edata['isPartOf']
            elif 'locatedIn' in edata:
                parent_id = edata['locatedIn']
            elif isinstance(edata.get('locatedIn'), list):
                parent_id = edata['locatedIn'][0]

            # プロパティのフラット化
            flat_props = flatten_properties(edata)
            
            # ID自体をプロパティとして保持
            flat_props['id'] = str(eid)
            
            # コンポーネントタイプ決定とスキーマ更新
            comp_type_id = category
            
            if category == 'EquipmentExt':
                raw_type = edata.get('deviceType', 'GenericEquipment')
                comp_type_id = sanitize_key(raw_type)
                
                if comp_type_id not in equipment_types:
                    equipment_types[comp_type_id] = {}
                
                for pk, pv in flat_props.items():
                    if pk not in equipment_types[comp_type_id]:
                        equipment_types[comp_type_id][pk] = get_twinmaker_type(pv)

            elif category == 'PointExt':
                comp_type_id = 'Point'
                for pk, pv in flat_props.items():
                    category_property_schema['Point'][pk] = get_twinmaker_type(pv)
                
                category_property_schema['Point'].update({
                    'category': 'STRING',
                    'point_type': 'STRING',
                    'unit': 'STRING',
                    'value': 'DOUBLE',
                    'state': 'STRING'
                })

            else: # Site, Building, Level, Space
                comp_type_id = category
                for pk, pv in flat_props.items():
                    category_property_schema[category][pk] = get_twinmaker_type(pv)

            # エンティティ情報の保存
            entities[eid] = {
                'name': edata.get('name', eid),
                'parent_id': parent_id,
                'component_type_id': comp_type_id,
                'properties': flat_props,
                'raw_data': edata
            }
            
    return {
        'category_property_schema': category_property_schema,
        'equipment_property_schema': equipment_types,
        'entities': entities,
        'hierarchy': hierarchy,
        'order': hierarchy_order
    }