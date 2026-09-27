# Shadowrocket Rules for v2rayN / v2rayNG

自动把 [Shadowrocket 上游规则](https://johnshall.github.io/Shadowrocket-ADBlock-Rules-Forever/sr_top500_banlist_ad.conf) 转换成：

- **v2rayN**：可从 GitHub Raw URL 导入的完整路由规则数组。
- **v2rayNG**：外部 GeoSite / GeoIP 资源 + 小型路由规则数组；容量允许时生成 JSON 本文二维码。

只合并连续的同类型、同 outbound 规则；不按 proxy/block 全局排序。精确去重保留首次出现位置，父域覆盖和 CIDR collapse 仅在连续组内进行。没有服务器、节点或用户凭据。

## v2rayN 使用方法

1. 打开“设置”→“路由设置”，添加或编辑一个专用规则集。
2. 在规则集编辑窗口填写 URL：
   `https://raw.githubusercontent.com/wangXiaohgithub/proxy/main/output/v2rayn/routing.json`
3. 点击 **“从订阅 Url 中导入规则”**。如已存在旧规则，选择替换而非追加，避免旧规则提前命中。
4. 保存规则集，在客户端选用该规则集。使用 Xray 内核。

文件是 `List<RulesItem>` 对应的 JSON **数组**，不是完整 Xray 配置，也不是包含 `routing` 的配置对象。明确写入 `enabled:true`；FINAL 为末尾 `port:"0-65535"`。不能把此文件直接作为 Xray 主配置启动。

## v2rayNG 使用方法

官方实现是资源和路由两个独立流程，不能一次扫码安装两者。请使用 Xray 内核。

**第一步：下载外部资源。**

侧边菜单 → **资源文件** → **添加** → **添加链接**（编辑页面标题“添加资产网址”）。分别填写以下项目并保存：

| 备注（必须与文件名完全一致） | URL |
| --- | --- |
| `g.dat` | `https://raw.githubusercontent.com/wangXiaohgithub/proxy/main/output/v2rayng/g.dat` |
| `i.dat` | `https://raw.githubusercontent.com/wangXiaohgithub/proxy/main/output/v2rayng/i.dat` |

点击资源页面“下载文件”按钮，确认下载成功。**“备注”就是资源在磁盘上的文件名**，不能写成“我的广告规则”之类的描述。没有 CIDR 数据时不生成 `i.dat`，也无需添加它。

**第二步：导入路由。**

打开“路由设置”页面中的规则集导入菜单：

- 若本次产物含 `output/v2rayng/routing.png`，选 **“从 QRcode 导入规则集”**，扫描 JSON 二维码。不要使用主页面的节点扫码入口。
- 若终端显示 `TOO LARGE`，打开下面的 routing URL，复制**完整 JSON 正文**，选择 **“从剪贴板导入规则集”**。仅复制 URL 无效。

`https://raw.githubusercontent.com/wangXiaohgithub/proxy/main/output/v2rayng/routing.json`

导入会替换未锁定的旧规则；客户端会保留已有锁定规则并放在新规则前面。要得到本项目的匹配顺序，请先检查/移除冲突的锁定规则，并检查客户端其他自动插入的路由。

**本次完整上游保留全部 60 个连续组，routing.json 为 2,845 字节，已生成并反向解码验证二维码。** 资源采用短文件名 `g.dat`（GeoSite）、`i.dat`（GeoIP），标签采用大写 base36；省略 remarks、空字段和 v2rayNG 默认 `enabled=true` 字段。官方 RulesetItem 的所有构造参数都有默认值，Kotlin 会生成无参构造器，Gson 使用该构造器，因此省略 enabled 后仍启用。Windows 版本仍明确写入 enabled:true。

![v2rayNG 路由二维码](output/v2rayng/routing.png)

二维码内容是完整 JSON 正文，不是 URL。先下载上述两个资源，再在路由设置中扫码。建议打开原图扫描；如果未来上游增长导致超过 2,953 字节，会明确报错提示并停止生成二维码，保留剪贴板导入作为后备。

资源文件与路由必须来自**同一次构建**。更新时先暂停代理服务，下载全部新资源，再导入相应路由并重新启动。不能只更新 dat 而永久沿用旧 routing.json：连续组标签可能变化。需要严格版本一致性时，将所有 Raw URL 中的 `main` 换成同一个 Git 提交 SHA，然后一起更新。

## 官方兼容性依据

2026-09-27 查询 GitHub Releases `latest`（稳定版本接口）并下载源码核对：v2rayN **7.24.9**、v2rayNG **2.2.6**、Xray-core **v26.3.27**。这是本次接口返回的版本，不代表测试了所有预发布版本或手机实机。

- [v2rayN ImportRulesFromUrl / AddBatchRoutingRulesAsync](https://github.com/2dust/v2rayN/blob/7.24.9/v2rayN/ServiceLib/ViewModels/RoutingRuleSettingViewModel.cs)：下载订阅 URL，反序列化为规则数组。
- [v2rayN RulesItem](https://github.com/2dust/v2rayN/blob/7.24.9/v2rayN/ServiceLib/Models/Entities/RulesItem.cs)：Enabled 默认 true；Windows 版本明确输出它。[中文 UI](https://github.com/2dust/v2rayN/blob/7.24.9/v2rayN/ServiceLib/Resx/ResUI.zh-Hans.resx)提供导入按钮名称。
- [v2rayNG RoutingSettingActivity](https://github.com/2dust/v2rayNG/blob/2.2.6/V2rayNG/app/src/main/java/com/v2ray/ang/ui/RoutingSettingActivity.kt) 将扫码文字和剪贴板文字交给 [SettingsManager.resetRoutingRulesets](https://github.com/2dust/v2rayNG/blob/2.2.6/V2rayNG/app/src/main/java/com/v2ray/ang/handler/SettingsManager.kt)，解析 `Array<RulesetItem>`，没有把 URL 下载成规则的步骤。
- [RulesetItem](https://github.com/2dust/v2rayNG/blob/2.2.6/V2rayNG/app/src/main/java/com/v2ray/ang/dto/entities/RulesetItem.kt)：remarks 可省略，domain/ip 使用字符串数组。资源 URL 不属于这个导入结构。
- [UserAssetUrlActivity](https://github.com/2dust/v2rayNG/blob/2.2.6/V2rayNG/app/src/main/java/com/v2ray/ang/ui/UserAssetUrlActivity.kt) 保存资源网址；[UserAssetViewModel](https://github.com/2dust/v2rayNG/blob/2.2.6/V2rayNG/app/src/main/java/com/v2ray/ang/viewmodel/UserAssetViewModel.kt) 下载到 `File(extDir, item.remarks)`；[CoreNativeManager](https://github.com/2dust/v2rayNG/blob/2.2.6/V2rayNG/app/src/main/java/com/v2ray/ang/core/CoreNativeManager.kt) 把用户资源目录交给内核。
- [Xray router.go](https://github.com/XTLS/Xray-core/blob/v26.3.27/infra/conf/router.go)：domain 和 ip 均支持 `ext:文件名:标签`，另外分别接受 `ext-domain:` / `ext-ip:`。标签查找会转大写，因此 dat 存储 `0`、`1`、`A`、`10` 等短大写 base36 标签。
- [Xray 官方 config.proto](https://github.com/XTLS/Xray-core/blob/v26.3.27/app/router/config.proto)：域名文件是 `GeoSiteList`，IP 文件是 `GeoIPList`；嵌套条目分别为 Domain 与 CIDR，不能混装成一个所谓通用 `sr_rules.dat`。

使用仓库内原样保存的官方 schema 与编译 descriptor，经固定版本 Python protobuf 序列化，不手写 protobuf wire format。日常构建不需要 Go 或 protoc。重新生成 descriptor 才需要 `grpcio-tools==1.75.1`，执行 `scripts/generate_descriptor.sh`。官方源文件许可证见 `vendor/xray/LICENSE`；上游规则权利归原作者，分发时请遵守上游许可。

`GEOIP,CN` 等仍保留 `geoip:cn` 引用客户端标准地理库，不把国家代码伪装成 CIDR。v2rayNG 当前会将 cn/private 重写到内置 `geoip-only-cn-private.dat`，请保持内置资源可用。自定义 GeoIP 仅包含源规则的具体 CIDR。

### 语义边界

转换保证受支持规则的**匹配内容与优先顺序**。未知规则、未知策略、空或损坏规则集、循环 RULE-SET、非末尾 FINAL 都会失败，不会静默丢弃。

不同客户端的 DNS 策略、嗅探、预置路由仍会影响实际流量。此项目不导入 Shadowrocket 的 General/DNS/Rewrite 配置；建议先按 `AsIs` 检查行为。`no-resolve` 等逐条选项没有在本格式中伪造对应字段，遇到它们明确报错，需人工确认适当转换策略。当前上游构建未出现这类选项。Reject 家族保持旧脚本的 block 映射，不模拟 Shadowrocket 的 HTTP 特定拒绝响应。

## 自动更新

`.github/workflows/update-rules.yml` 每日 UTC 18:00（北京时间次日 02:00）运行，也支持手动触发。安装固定依赖 → 单测 → 下载/转换 → JSON/dat/QR 校验 → 固定版本 Xray 实际加载 → 重复构建对比 → 有产物变化才提交。

权限为 `contents: write`，提交信息为 `chore: update proxy rules`。仅 schedule/workflow_dispatch 触发，没有 push 触发，因此机器人提交不会形成循环。同分支工作流串行执行，不强推；远端冲突时 push 失败交由维护者处理。受保护分支可能阻止机器人写入，需要按仓库策略调整。

所有 RULE-SET 下载失败都会终止。curl 带重试、重试延迟、连接/总超时和 HTTPS 限制；缓存只在单次构建内复用，不回退到过期规则。转换先在临时目录完成验证，成功后只替换受管理文件，保留其他文件。磁盘故障时文件级替换不等同于多文件事务；CI 失败不会提交发布。

源内容和环境相同，输出字节一致；统计没有构建时间戳。`output/stats.json` 保存输入 SHA256、组数、优化数量、文件大小和二维码状态。

转换器从 `GITHUB_REPOSITORY` 获取 owner/repo，打印真实 Raw URL；本地未设置时打印 owner/repo 占位符。本次实际链接也自动写入 [output/README.md](output/README.md)。非 main 分支可设置 `RULES_BRANCH`。用户名不写死在代码中。

## 手动更新

GitHub 仓库 → Actions → **Update Rules** → **Run workflow**。

## 本地运行

推荐 Python 3.12（CI 与本机验证版本），curl 需在 PATH 中：

```sh
cd /Users/ansrih/code/proxy
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python3 convert.py
python -m unittest discover -s tests -v
python convert.py --validate-only
python scripts/check_determinism.py
python scripts/fetch_xray.py
python scripts/smoke_xray.py --xray .work/xray/xray --geoip .work/xray/geoip.dat
```

本机已建立 `.venv`，可直接使用 `.venv/bin/python convert.py`，无需修改系统 Python。`--source-file path.conf` 可使用本地主配置；其中的 RULE-SET 仍会下载。`--output path` 可指定输出目录。

## 输出与模块

```text
convert.py                 CLI、暂存校验与发布
src/parser.py              严格解析与 RULE-SET 展开
src/downloader.py          curl 下载与构建内缓存
src/optimizer.py           保留原脚本的去重、父域覆盖、CIDR、连续分组算法
src/dat_builder.py         官方 protobuf 生成与反向读取
src/qr.py                  QR L 编码、容量检查与解码
src/validate.py            结构、FINAL、ext、组内容等价校验
vendor/xray/               固定官方 proto、descriptor、许可证
scripts/                   Xray smoke test、下载校验、确定性检查
output/
  v2rayn/routing.json
  v2rayng/routing.json
  v2rayng/g.dat
  v2rayng/i.dat      有 CIDR 才生成
  v2rayng/routing.png       不超过 2953 字节且解码成功才生成
  debug/proxy_domains.txt
  debug/block_domains.txt
  debug/direct_domains.txt
  debug/proxy_ips.txt
  stats.json
```

TXT 保留 `domain:`、`full:` 和 keyword 匹配含义，仅用于人工检查，不能把这些跨组列表当成正式路由。原始脚本备份在 `.backup/convert.original.py`（Git 忽略）；原 `output/` 根目录旧产物保留作对照，新流程仅分发新子目录。

## 发布到 GitHub

仓库： https://github.com/wangXiaohgithub/proxy 。维护更新时先检查代码和输出：

```sh
git status
git add convert.py src scripts tests vendor requirements.txt README.md .gitignore .github output/v2rayn output/v2rayng output/debug output/stats.json output/README.md
git commit -m "feat: add GitHub rule distribution for v2rayN and v2rayNG"
git push
```

建议显式添加新分发目录，避免误提交保留的旧根目录产物。首次上传后，在 GitHub 上手动运行一次工作流，确认仓库写权限及受保护分支策略；本地检查不能替代远端实际运行结果。
