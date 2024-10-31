import os
import sys

import requests

OFFICIAL_OBSIDIAN_REPO_OWNER = 'obsidianmd'  # Obsidian官方仓库
OFFICIAL_OBSIDIAN_REPO_NAME = 'obsidian-releases'  # Obsidian官方仓库
THIS_REPO_OWNER = 'YuanWeiSite'  # 此仓库
THIS_REPO_NAME = 'Obsidian-Android-Patch'  # 此仓库
NEW_PACKAGE_NAME = 'site.yuanwei.md.obsidian'  # apk新的包名


# 获取某仓库的最新release的详细信息
def get_latest_release_info(repo_owner, repo_name):
    api_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest'
    response = requests.get(api_url)
    if response.status_code == 200:
        release_info = response.json()
        return release_info
    else:
        print(f"Failed to retrieve data: {response.status_code}")


# 获取Obsidian官方仓库最新release的tag和apk文件下载链接
def get_official_obsidian_repo_tag_and_apk_url():
    release_info = get_latest_release_info(OFFICIAL_OBSIDIAN_REPO_OWNER, OFFICIAL_OBSIDIAN_REPO_NAME)
    for asset in release_info['assets']:
        if str(asset['name']).endswith('apk'):
            return release_info['tag_name'], asset['browser_download_url']


# 获取此仓库的最新release的tag
def get_this_repo_tag():
    release_info = get_latest_release_info(THIS_REPO_OWNER, THIS_REPO_NAME)
    return release_info['tag_name']


# 下载文件到指定位置
def download_file(url, file_name):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            with open(file_name, 'wb') as file:
                file.write(response.content)
            print(f"File downloaded and saved as {file_name}")
        else:
            print(f"Failed to download file: {response.status_code}")
    except Exception as e:
        print(f"An error occurred: {e}")


# 以字符串替换的方式处理配置文件
# 不标准，但可以避免特定XML配置文件解析/还原时出现问题
def config_replace(file_path, old_value, new_value, max_count=1):
    try:
        with open(file_path, 'r') as file:
            content = file.read()
        new_content = (
            content.replace(old_value, new_value, max_count))
        with open(file_path, 'w') as file:
            file.write(new_content)
    except Exception as e:
        print(f"An error occurred: {e}")


# 修改apk文件
# 添加信任用户证书
# 修改包名
# # input_apk_name 输入的apk文件名，不包含后缀
# # output_apk_name 输出的apk文件名，不包含后缀
def patch_apk(input_apk_name, output_apk_name):
    # 下载apktool
    download_file('https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.10.0.jar', 'apktool.jar')

    # 解包
    os.system(f'java -jar apktool.jar d {input_apk_name}.apk')

    # 添加信任用户证书
    # # 添加network_security_config.xml文件
    xml_content = '''<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
  <base-config cleartextTrafficPermitted="true">
    <trust-anchors>
      <certificates src="system" />
      <certificates src="user" />
    </trust-anchors>
  </base-config>
</network-security-config>'''
    try:
        with open(input_apk_name + '/res/xml/network_security_config.xml', 'w') as file:
            file.write(xml_content)
    except Exception as e:
        print(f"An error occurred: {e}")

    # # 编辑AndroidManifest.xml
    config_replace(input_apk_name + '/AndroidManifest.xml', '<application',
                   '<application android:networkSecurityConfig="@xml/network_security_config"')

    # 修改包名
    # # 编辑apktool.yml
    config_replace(input_apk_name + '/apktool.yml', 'renameManifestPackage: null',
                   f'renameManifestPackage: {NEW_PACKAGE_NAME}')

    # 重新打包
    os.system(f'java -jar apktool.jar b {input_apk_name} -o {input_apk_name}.apk')

    # 准备zipalign
    os.system('chmod +x ./zipalign')

    # zip对齐
    os.system(f'./zipalign -v 4 {input_apk_name}.apk zip.apk')

    # 签名
    os.system(
        f'java -jar ./apksigner.jar sign --ks ks.keystore --ks-pass pass:000000 --out {output_apk_name}.apk zip.apk')


# 创建一个release
def create_release(repo_owner, repo_name, tag_name, token):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "tag_name": tag_name,
        "target_commitish": "main",
        "name": tag_name,
        "body": "Patched Obsidian",
        "draft": False,
        "prerelease": False
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201:
        return response.json()['id']
    else:
        raise Exception(f"Failed to create release: {response.status_code}, {response.text}")


# 向release上传文件
def upload_asset_to_release(repo_owner, repo_name, release_id, file_path, token, file_name):
    url = f"https://uploads.github.com/repos/{repo_owner}/{repo_name}/releases/{release_id}/assets"
    headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/octet-stream",
        "Accept": "application/vnd.github.v3+json"
    }
    params = {
        "name": file_name
    }
    with open(file_path, 'rb') as file:
        response = requests.post(url, headers=headers, params=params, data=file)
    if response.status_code != 201:
        raise Exception(f"Failed to upload asset: {response.status_code}, {response.text}")


if __name__ == '__main__':
    if len(sys.argv) == 2:
        github_token = sys.argv[1]
        obsidian_tag, obsidian_url = get_official_obsidian_repo_tag_and_apk_url()
        yuanwei_tag = get_this_repo_tag()
        if yuanwei_tag != obsidian_tag:
            original_apk = 'obsidian'
            patched_apk = 'patched'
            download_file(obsidian_url, original_apk + '.apk')
            patch_apk(original_apk, patched_apk)
            try:
                release_id_ = create_release(THIS_REPO_OWNER, THIS_REPO_NAME, obsidian_tag, github_token)
                print(f"New Release ID: {release_id_}")
                upload_asset_to_release(THIS_REPO_OWNER, THIS_REPO_NAME, release_id_, patched_apk + '.apk',
                                        github_token,
                                        f'Obsidian-{obsidian_tag}-Patched.apk')
                print("File uploaded successfully.")
            except Exception as e_:
                print(e_)
        else:
            print('Latest version.')
    else:
        print('sys.argv != 2')
