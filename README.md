# TwinMaker LinkML Importer

LinkML形式（YAML）で記述された建物・設備データモデルを、AWS IoT TwinMakerのワークスペースにインポートするツールキットです。

## 概要

このプロジェクトは、YAMLファイルで定義された「サイト構造」「建物」「部屋」「設備（センサー情報含む）」を読み込み、AWS IoT TwinMaker上で以下のリソースを自動生成します。

1.  **Component Types (コンポーネントタイプ)**: 設備の型定義（エアコン、照明、センサーなど）。
2.  **Entities (エンティティ)**: 階層構造（Site > Building > Floor > Room > Equipment）。
3.  **Components (コンポーネント)**: 各エンティティに紐づく属性データ。

## ディレクトリ構成

```text
twinmaker-linkml-importer/
├── data/
│   └── buildingA.yaml         # インポート元のデータファイル
├── common.py                  # 共通ロジック・設定読み込み
├── cleanup_all.py             # [リセット用] 全リソース削除スクリプト
├── create_types.py            # [Step 1] コンポーネントタイプ作成
├── create_entities.py         # [Step 2] エンティティ（箱）作成
├── attach_components.py       # [Step 3] コンポーネント（中身）紐付け
├── .env                       # 環境変数設定ファイル（Git除外）
├── requirements.txt           # 依存ライブラリ一覧
└── README.md                  # 本ファイル
```

## 事前準備

*   Python 3.8 以上
*   AWSアカウントと、適切な権限を持つIAMユーザー/ロール
    *   `iottwinmaker:*` 権限が必要です。
*   AWS IoT TwinMaker ワークスペース作成済みであること

## 環境構築

### 1. 仮想環境の作成とライブラリインストール

```bash
# 仮想環境の作成
python -m venv venv

# 仮想環境の有効化
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# ライブラリのインストール
pip install -r requirements.txt
```

### 2. 環境変数の設定

ルートディレクトリに `.env` ファイルを作成し、以下の内容を記述してください。

```ini
# AWSリージョン
AWS_DEFAULT_REGION=ap-northeast-1

# TwinMakerのワークスペースID
TWINMAKER_WORKSPACE_ID=MySmartBuildingWorkspace

# 入力ファイルパス
INPUT_FILE=data/buildingA.yaml

# (オプション) AWS CLIの設定をしていない場合のみ以下を記述
# AWS_ACCESS_KEY_ID=AKIA...
# AWS_SECRET_ACCESS_KEY=...
# AWS_SESSION_TOKEN=... (MFA使用時のみ)
```

## 実行手順

データの整合性を保ち、APIエラー（ResourceNotFound等）を防ぐため、処理は3段階に分かれています。**必ず順番に実行してください。**

### Step 0: 環境のリセット（推奨）

既存のデータと衝突しないよう、ワークスペース内のデータを一度クリーンアップします。

```bash
python cleanup_all.py
```

### Step 1: 型定義の作成 (Component Types)

YAML内の `deviceType` やクラス定義に基づき、コンポーネントタイプを作成します。

```bash
python create_types.py
```
*   **確認:** ログに `[OK] Created: ...` と表示されることを確認してください。

### Step 2: エンティティ階層の作成 (Entities)

親子の階層構造（サイト > 建物 > 部屋...）を持つエンティティ（箱）を作成します。

```bash
python create_entities.py
```

### Step 3: データの実装 (Components)

作成されたエンティティに対して、コンポーネント（属性値）を紐付けます。

```bash
python attach_components.py
```

すべてのステップが完了すると、AWSコンソール上で階層構造とプロパティが確認できます。

## 注意事項

*   **データ型について**: 現在の仕様では、エラー回避のためすべてのプロパティを「静的データ（Static）」として作成しています。SiteWise等の時系列データと連携する場合は、`create_types.py` 内の `isTimeSeries` 設定を変更してください。
*   **API制限**: 大量のデータをインポートする場合、AWS APIのレートリミット（スロットリング）にかかる可能性があります。スクリプト内の `time.sleep()` の値を調整してください。

## トラブルシューティング

*   **Authentication Error**: `.env` ファイルの記述、または AWS CLI の設定（`aws configure`）を確認してください。
*   **Abstract ComponentType Error**: 型定義が「抽象クラス」として作成されています。Step 0 (Cleanup) を実行した後、Step 1 を再実行してください。
*   **ValidationException (Entity does not exist)**: 作成の反映待ち（ラグ）が原因です。Step 2 と Step 3 を別々に実行することで解消されます。
