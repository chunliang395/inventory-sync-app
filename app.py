from flask import Flask, request, render_template, send_file
import os
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta

app = Flask(__name__)

# -----------------------------
# 1) 主要資料夾設定
# -----------------------------
UPLOAD_FOLDER = 'uploaded_files'
RECORD_FOLDER = 'records'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def ensure_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)

def clean_old_files(folder, days=7):
    now = datetime.now()
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        if os.path.isdir(filepath):
            clean_old_files(filepath, days)
        else:
            mtime = os.path.getmtime(filepath)
            mtime_dt = datetime.fromtimestamp(mtime)
            if (now - mtime_dt) > timedelta(days=days):
                os.remove(filepath)

def compare_dataframes(df_before, df_after, sku_col):
    """
    比對 [Inventory, Track Inventory]，只列出真正有異動的商品。
    """
    compare_cols = ["Inventory", "Track Inventory"]
    merged = pd.merge(df_before, df_after, on=sku_col, how='outer', suffixes=("_old","_new"))
    diffs = []
    for _, row in merged.iterrows():
        sku_val = row[sku_col]
        changed = False
        diff_info = {sku_col: sku_val}
        for col in compare_cols:
            old_val = row.get(col + "_old", None)
            new_val = row.get(col + "_new", None)
            if old_val != new_val:
                changed = True
                diff_info[col + "_Before"] = old_val
                diff_info[col + "_After"]  = new_val
        if changed:
            diffs.append(diff_info)
    return pd.DataFrame(diffs)

@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        file1 = request.files.get('file1')  # 官網檔
        file2 = request.files.get('file2')  # 廠商檔
        if not file1 or not file2:
            return "請同時上傳【官網檔案】與【廠商檔案】！", 400

        ensure_folder(UPLOAD_FOLDER)
        p1 = os.path.join(UPLOAD_FOLDER, file1.filename)
        p2 = os.path.join(UPLOAD_FOLDER, file2.filename)
        file1.save(p1)
        file2.save(p2)

        # 讀取官網檔 (header=0)
        df_before = pd.read_excel(p1, header=0)

        # 取得前端廠商選擇
        selected_vendor = request.form.get('vendor_selection','').strip()
        # 若前端下拉是 "Light" => 改成 "Light in the Attic"
        if selected_vendor == "Light":
            selected_vendor = "Light in the Attic"

        # 官網中 "Tags" 欄位，若 == "即將發行" => 不更新
        tags_col = "Tags"

        # =====================================================
        # (1) Light in the Attic 區塊 (邏輯不動)
        # =====================================================
        if selected_vendor == "Light in the Attic":
            df_vendor = pd.read_excel(p2, header=1)  # 跳過第一行

            vendor_col = "Vendor"
            sku_col    = "SKU"
            inv_col    = "Inventory"
            track_col  = "Track Inventory"
            ac_col     = "Option1 Value"

            if "SKU" not in df_vendor.columns or "INV AVAIL" not in df_vendor.columns:
                return f"LITA檔案需 SKU & INV AVAIL，目前={df_vendor.columns}",400

            vendor_sku_dict = {}
            for i, rv in df_vendor.iterrows():
                skv = str(rv["SKU"]).strip()
                vendor_sku_dict[skv] = True

            df_after = df_before.copy()
            for i, rowa in df_after.iterrows():
                vend_str = str(rowa.get(vendor_col,"")).strip().lower()
                if vend_str == "light in the attic":
                    opt_str = str(rowa.get(ac_col,"")).strip()
                    if opt_str == "預購":
                        # 原先 LITA 不判斷 '即將發行'
                        sk = str(rowa.get(sku_col,"")).strip()
                        trk= str(rowa.get(track_col,"")).strip().lower()
                        if sk not in vendor_sku_dict:
                            df_after.at[i, inv_col] = 0
                            if trk != "yes":
                                df_after.at[i, track_col] = "Yes"

            # 現貨補抓 ...
            df_main_lita = df_after[df_after[vendor_col].str.lower()=="light in the attic"].copy()
            pre_skus = set(df_main_lita.loc[df_main_lita[ac_col]=="預購", sku_col])

            mask_extra = (
                df_after[sku_col].isin(pre_skus) &
                (df_after[ac_col] == "現貨") &
                df_after[sku_col].notna() &
                (df_after[sku_col].str.strip() != "")
            )
            df_extra = df_after[mask_extra].copy()

            df_after_lita = pd.concat([df_main_lita, df_extra], ignore_index=True).drop_duplicates()
            sort_map = {"預購":0,"現貨":1}
            df_after_lita["__sort_order"] = df_after_lita[ac_col].map(sort_map).fillna(2)
            df_after_lita = df_after_lita.sort_values([sku_col,"__sort_order"]).reset_index(drop=True)
            df_after_lita.drop(columns=["__sort_order"], inplace=True)

            df_before_lita = df_before[df_before[vendor_col].str.lower()=="light in the attic"].copy()
            df_diff = compare_dataframes(df_before_lita, df_after_lita, sku_col)

            ensure_folder(RECORD_FOLDER)
            ds = datetime.now().strftime("%Y%m%d")
            up_dir = os.path.join(RECORD_FOLDER, f"{ds}_upload")
            diff_dir= os.path.join(RECORD_FOLDER, f"{ds}_diff")
            ensure_folder(up_dir)
            ensure_folder(diff_dir)

            up_filename= f"upload_{datetime.now().strftime('%H%M%S')}.xlsx"
            up_filepath= os.path.join(up_dir, up_filename)
            with pd.ExcelWriter(up_filepath, engine='openpyxl') as w:
                df_after_lita.to_excel(w, index=False)

            diff_filename= f"diff_{datetime.now().strftime('%H%M%S')}.xlsx"
            diff_filepath= os.path.join(diff_dir, diff_filename)
            with pd.ExcelWriter(diff_filepath, engine='openpyxl') as w:
                df_diff.to_excel(w, index=False)

            clean_old_files(RECORD_FOLDER, days=7)

            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as w:
                df_after_lita.to_excel(w, index=False)
            output.seek(0)
            return send_file(
                output,
                as_attachment=True,
                download_name='updated_official_lita_only.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

        # =====================================================
        # (2) Juno 區塊 => 若 Tags="即將發行" => 不更新
        # =====================================================
        elif selected_vendor == "Juno":
            df_vendor = pd.read_excel(p2, header=0)
            vendor_col = "Vendor"
            sku_col    = "SKU"
            inv_col    = "Inventory"
            track_col  = "Track Inventory"
            ac_col     = "Option1 Value"

            if "Cat No" not in df_vendor.columns or "Stock" not in df_vendor.columns:
                return f"Juno檔案需 Cat No, Stock，目前={df_vendor.columns}",400

            # 建 dict => {catNo => stock}
            juno_dict = {}
            for i, rowv in df_vendor.iterrows():
                cat_no_val= str(rowv["Cat No"]).strip()
                stock_val = rowv["Stock"]
                juno_dict[cat_no_val] = stock_val

            df_after = df_before.copy()

            # (A) 篩選出「(Vendor=Juno & Option=預購) & (Tags != '即將發行')」的行才更新
            #     其餘行 => 不更新
            mask_juno_update = (
                df_after[vendor_col].str.strip().str.lower()=="juno"
            ) & (
                df_after[ac_col].str.strip()=="預購"
            ) & (
                df_after[tags_col].str.strip().str.lower()!="即將發行"
            )

            # (B) 逐行更新 => 庫存、Track=Yes
            idx_to_update = df_after[mask_juno_update].index
            for i in idx_to_update:
                row_ = df_after.loc[i]
                rsku = str(row_[sku_col]).strip()
                if rsku in juno_dict:
                    df_after.at[i, inv_col] = juno_dict[rsku]
                else:
                    df_after.at[i, inv_col] = 0
                df_after.at[i, track_col] = "Yes"

            # (C) 同SKU 現貨補抓
            df_main_juno = df_after[df_after[vendor_col].str.lower()=="juno"].copy()
            pre_skus = set(df_main_juno.loc[df_main_juno[ac_col]=="預購", sku_col])

            mask_extra = (
                df_after[sku_col].isin(pre_skus) &
                (df_after[ac_col] == "現貨") &
                df_after[sku_col].notna() &
                (df_after[sku_col].str.strip() != "")
            )
            df_extra = df_after[mask_extra].copy()

            df_after_juno = pd.concat([df_main_juno, df_extra], ignore_index=True).drop_duplicates()

            sort_map = {"預購":0,"現貨":1}
            df_after_juno["__sort_order"] = df_after_juno[ac_col].map(sort_map).fillna(2)
            df_after_juno = df_after_juno.sort_values([sku_col,"__sort_order"]).reset_index(drop=True)
            df_after_juno.drop(columns=["__sort_order"], inplace=True)

            # 差異檔 => 只比對 (Vendor=Juno)
            df_before_juno = df_before[df_before[vendor_col].str.lower()=="juno"].copy()
            df_diff = compare_dataframes(df_before_juno, df_after_juno, sku_col)

            ensure_folder(RECORD_FOLDER)
            ds = datetime.now().strftime("%Y%m%d")
            up_dir  = os.path.join(RECORD_FOLDER, f"{ds}_upload")
            diff_dir= os.path.join(RECORD_FOLDER, f"{ds}_diff")
            ensure_folder(up_dir)
            ensure_folder(diff_dir)

            up_filename= f"upload_{datetime.now().strftime('%H%M%S')}.xlsx"
            up_filepath= os.path.join(up_dir, up_filename)
            with pd.ExcelWriter(up_filepath, engine='openpyxl') as w:
                df_after_juno.to_excel(w, index=False)

            diff_filename= f"diff_{datetime.now().strftime('%H%M%S')}.xlsx"
            diff_filepath= os.path.join(diff_dir, diff_filename)
            with pd.ExcelWriter(diff_filepath, engine='openpyxl') as w:
                df_diff.to_excel(w, index=False)

            clean_old_files(RECORD_FOLDER, days=7)

            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as w:
                df_after_juno.to_excel(w, index=False)
            output.seek(0)

            return send_file(
                output,
                as_attachment=True,
                download_name='updated_official_juno_only.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

        else:
            return f"不支援廠商: {selected_vendor}",400

    else:
        return render_template('index.html')

if __name__ == '__main__':
    ensure_folder(UPLOAD_FOLDER)
    ensure_folder(RECORD_FOLDER)
    app.run(debug=True)