---
title: "우분투 22.04 화면 색감이 빨갛게(redish) 나오는 문제 해결 방법"
url: "https://frankler.tistory.com/3766"
created_at: "Tue, 16 May 2023 11:06:18 +0900"
event_dates:
category: ""
tags:
---

# 우분투 22.04 화면 색감이 빨갛게(redish) 나오는 문제 해결 방법

<p style="text-align: left;">본 페이지에서는 우분투 22.04에서 화면이 빨갛게 나오는 문제를 해결하는 방법에 대해서 기록하고자 합니다. <br /><br /></p><h2 style="text-align: left;">[환경]</h2><p style="text-align: left;">- 운영체제 : Ubuntu 22.04<br />- 비디오 카드 : NVIDIA GA104 [GeForce RTX 3060 Ti Lite Hash Rate]<br />- 모니터1 : HP M27fw (HDMI)<br />- 모니터2 : HP E233 (DP)<br /><br /></p><h2 style="text-align: left;">[문제의 상황]</h2><p style="text-align: left;">- 기존에는 DP(Display Port)를 이용해서 듀얼 모니터를 잘 사용하고 있었습니다. <br />- 하지만 모니터 하나를 DP에서 HDMI로 변경해서 연결했더니 아래 화면처럼 화면이 빨갛게 표시되기 시작했습니다. <br /><br /></p><h2 style="text-align: left;">[시도해본 것들]</h2><p style="text-align: left;">- 재부팅을 시도해봤습니다. (해결 안됨)<br />- 모니터1을 분리하고 모니터 2만 연결해봤습니다. (해결 안됨)<br />- 모니터2를 분리하고 모니터 1만 연결해봤습니다. (해결 안됨)<br /><br /></p><figure class="imageblock alignCenter"><span><img height="2326" src="https://blog.kakaocdn.net/dn/FQfCg/btsf6EmJM57/HyW3RA4Gg9mwtJ2DB1f5lK/img.jpg" width="3890" /></span></figure>
<h2 style="text-align: left;"><br />[검색해본 것들]</h2><p style="text-align: left;">아래의 검색 키워드들로 검색해봤습니다. <br />- ubuntu redish color<br />- ubuntu pink tilt<br />Stack Overflow 같은 페이지에 색상 프로파일을 삭제하도록 가이드가 있었으나 설정에 들어가도 색상 프로파일을 삭제하는 화면을 찾을 수 없었습니다. <br /><br /></p><h2 style="text-align: left;">[해결 방법]</h2><p style="text-align: left;">1. 엔비디아 셋팅 설치 (nvidia-settings)</p><pre class="bash"><code>$ sudo apt-get install nvidia-settings</code></pre><p style="text-align: left;">2. 재부팅</p><pre class="bash"><code>$ sudo reboot</code></pre><p style="text-align: left;"><br />제 경우는 위의 방법으로 깔끔하게 해결할 수 있었습니다. <br /><br />이상입니다. </p>