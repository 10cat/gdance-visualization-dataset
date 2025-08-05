from huggingface_hub import upload_folder

upload_folder(
    folder_path="path/to/your/data",
    repo_id="YLinca/gdance-visualizations",  # ✅ 带上用户名
    repo_type="dataset",
    # token="your_hf_token"  # 如果没有登录 CLI，就加上这一行
)