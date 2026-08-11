---
title: "{{ replace .Name "-" " " | title }}"
date: {{ .Date }}
description: ""
tags: []
draft: true
# faq 는 선택이다. 넣을 때는 2~3개, 본문이 실제로 답한 질문만.
# faq:
#   - q: "질문 한 문장"
#     a: "답 두세 문장. 본문에 없는 사실을 새로 만들지 않는다."
# source_url: "원문 기사 URL"
# related_articles:   # 선택. 선별 결과가 없으면 필드 자체를 생략한다(빈 배열 금지).
#   - title: "기사 제목"
#     url: "https://..."
#     source: "언론사 표시명"
---
