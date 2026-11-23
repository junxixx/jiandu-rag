可选 GLB 放置规则（Vite 静态资源，路径 /models/chat/…）：



1) 按角色：文件名必须与后端 role_key 一致：

   li_gan.glb、shang_guan.glb、ban_chao.glb、geng_gong.glb、zhang_qian.glb、fu_jiezi.glb



2) 当前工程内六席模型来源约定（可自行覆盖替换）：

   · li_gan      ← Ligan.glb（戍卒李敢）

   · shang_guan  ← daobili.glb（刀笔吏）

   · ban_chao    ← shangguanjie.glb（若与班超形象不符，可另导出覆盖 ban_chao.glb）

   · geng_gong   ← genggong.glb

   · zhang_qian  ← zhangqian.glb

   · fu_jiezi    ← fujiezi.glb



3) 通用兜底：idle.glb（无专属文件时尝试加载）。

若均失败，边塞夜话「烽影」使用程序生成的低面占位模型。



建议：单文件尽量压缩（目标 < 5MB 更易首屏），Draco/meshopt 更佳。



对话联动：GLB 内多条动画片段按名称匹配并淡入淡出：

  · 思考：think / ponder / 思考 / 想 / 凝 / 默 / 斟酌 …

  · 答问：talk / speak / 说话 / 答 / 讲 / 谈 / 演讲 …

  · 待机：idle / stand / 待机 / 休闲 / 站立 / 基础 …

仅一条动画时，仍叠加外层轻微晃动表现节奏。



弱网或大文件首包较慢，属正常现象。


