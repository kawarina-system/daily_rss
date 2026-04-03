import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# 設定
RSS_URL = "https://j-net21.smrj.go.jp/snavi/support/support.xml"

def merge_xml_monthly():
    # 1. 現在の年月を取得してファイル名を決定
    now = datetime.now()
    ym_str = now.strftime('%Y%m')  # 例: 202405
    save_file = f"{ym_str}integrated_support.xml"
    
    print(f"[{now}] 処理を開始します（対象ファイル: {save_file}）")

    # 2. 最新のXMLを取得
    try:
        response = requests.get(RSS_URL)
        response.raise_for_status()
        remote_root = ET.fromstring(response.content)
    except Exception as e:
        print(f"エラー: XMLの取得に失敗しました。 {e}")
        return

    # 3. 保存用ファイルの読み込み（存在しない場合は新規作成）
    if os.path.exists(save_file):
        local_tree = ET.parse(save_file)
        local_root = local_tree.getroot()
    else:
        # 新規月の場合：リモートの構造をコピーして中身（item）を空にする
        print(f"新規月のファイルを作成します: {save_file}")
        local_root = ET.fromstring(response.content)
        channel = local_root.find("channel")
        for item in channel.findall("item"):
            channel.remove(item)
        local_tree = ET.ElementTree(local_root)

    channel = local_root.find("channel")
    
    # 重複チェック用の既存リンク取得
    existing_links = {
        item.find("link").text for item in channel.findall("item") 
        if item.find("link") is not None
    }

    # 4. 新しいアイテムを追加
    new_count = 0
    remote_items = remote_root.findall(".//item")
    
    # 古い順に追加するためにreversedを使用
    for item in reversed(remote_items):
        link = item.find("link").text if item.find("link") is not None else ""
        if link and link not in existing_links:
            channel.append(item)
            existing_links.add(link)
            new_count += 1

    # 5. 保存
    # GitHub Actionsでの競合を避けるため、整形して保存
    local_tree.write(save_file, encoding="utf-8", xml_declaration=True)
    print(f"完了: {new_count} 件の新しいアイテムを {save_file} に追加しました。")

if __name__ == "__main__":
    merge_xml_monthly()