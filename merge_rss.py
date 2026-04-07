import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

# 設定
RSS_URL = "https://j-net21.smrj.go.jp/snavi/support/support.xml"

def _parse_item_datetime(text: str) -> datetime | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None

def _get_item_datetime(item: ET.Element) -> datetime | None:
    # RSSの実体が pubDate ではなく dc:date の場合がある
    date_text = (
        item.findtext("pubDate")
        or item.findtext("./{*}date")  # e.g. <dc:date>...</dc:date>
        or item.findtext("date")
    )
    return _parse_item_datetime(date_text)

def merge_xml_monthly():
    # 1. 現在の年月を取得
    now = datetime.now()
    ym_str = now.strftime('%Y%m')  # 例: 202405
    save_file = "integrated_support.xml"

    print(f"[{now}] 処理を開始します（対象ファイル: {save_file} / 当月: {ym_str}）")

    # 2. 最新のXMLを取得
    try:
        response = requests.get(RSS_URL)
        response.raise_for_status()
        remote_root = ET.fromstring(response.content)
    except Exception as e:
        print(f"エラー: XMLの取得に失敗しました。 {e}")
        return

    # 3. 月替わり判定（既存 integrated_support.xml に当月itemが無ければ先月として退避）
    if os.path.exists(save_file):
        try:
            current_tree = ET.parse(save_file)
            current_root = current_tree.getroot()
            current_channel = current_root.find("channel")

            has_current_month_item = False
            if current_channel is not None:
                for item in current_channel.findall("item"):
                    dt = _get_item_datetime(item)
                    if dt is None:
                        continue
                    if dt.strftime("%Y%m") == ym_str:
                        has_current_month_item = True
                        break

            if not has_current_month_item:
                last_month_ym = (now.replace(day=1) - timedelta(days=1)).strftime("%Y%m")
                archive_file = f"{last_month_ym}integrated_support.xml"
                if not os.path.exists(archive_file):
                    os.replace(save_file, archive_file)
                    print(f"月が変わったため退避しました: {save_file} -> {archive_file}")
        except Exception as e:
            # 退避処理に失敗しても、本体のマージ処理自体は続行する
            print(f"警告: 月替わり退避処理に失敗しました（続行します）。 {e}")

    # 4. 保存用ファイルの読み込み（存在しない場合は新規作成）
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

    # 5. 新しいアイテムを追加
    new_count = 0
    remote_items = remote_root.findall(".//item")
    
    # 古い順に追加するためにreversedを使用
    for item in reversed(remote_items):
        link = item.find("link").text if item.find("link") is not None else ""
        if link and link not in existing_links:
            channel.append(item)
            existing_links.add(link)
            new_count += 1

    # 6. 保存
    # GitHub Actionsでの競合を避けるため、整形して保存
    local_tree.write(save_file, encoding="utf-8", xml_declaration=True)
    print(f"完了: {new_count} 件の新しいアイテムを {save_file} に追加しました。")

if __name__ == "__main__":
    merge_xml_monthly()