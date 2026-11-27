# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""发布器（可选扩展）：把打包好的原型推送到某个托管服务，成功后用 lib.demo.record_online() 写回地址。

约定见 references/publish.md §3。核心流程不依赖任何发布器。
"""
