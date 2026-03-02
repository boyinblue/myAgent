---
title: "우분투 22.04에서 systemd-resolve 명령어를 찾을 수 없을 경우 문제 해결 방법"
url: "https://worldclassproduct.tistory.com/entry/%EC%9A%B0%EB%B6%84%ED%88%AC-2204%EC%97%90%EC%84%9C-systemd-resolve-%EB%AA%85%EB%A0%B9%EC%96%B4%EB%A5%BC-%EC%B0%BE%EC%9D%84-%EC%88%98-%EC%97%86%EC%9D%84-%EA%B2%BD%EC%9A%B0-%EB%AC%B8%EC%A0%9C-%ED%95%B4%EA%B2%B0-%EB%B0%A9%EB%B2%95"
created_at: "Thu, 8 Sep 2022 13:58:24 +0900"
event_dates:
category: ""
tags:
comments: "<p><figure class="imageblock alignCenter"><span><img height="1036" src="https://blog.kakaocdn.net/dn/dmDCbx/btrLFHHXWHV/zkaHkn7K7rykXVPElGdci1/img.jpg" width="1109" /></span></figure>
</p>
<p>&nbsp;</p>
<p>우분투 리눅스 20.04에서 22.04로 업그레이드 이후에 많은 문제들이 발생을 했습니다. proftpd 패키지를 업그레이드할 수 없는 문제, 한글을 입력할 수 없는 문제, 도메인 네임을 제대로 가져올 수 없는 문제 등 여러가지 문제들을 만났고, 결국 모두 해결해 낼 수 있었습니다.</p>
<p>오늘은 우분투 22.04 리눅스에서 발견한 사소한 문제에 대해서 기록해두고자 합니다. 20.04에서 잘 사용하던 "systemd-resolve --status"명령을 22.04에서는 더이상 사용할 수 없습니다.</p>
<p>&nbsp;</p>
<h2>22.04에서 "systemd-resolve --status" 명령 실행(X)</h2>
<pre class="bash" id="code_1662612588762"><code>$ systemd-resolve --status</code></pre>
<p>우분투 리눅스 22.04에서 위의 명령을 실행하면 아래와 같은 에러 메시지가 발생합니다.</p>
<table border="1" style="border-collapse: collapse; width: 100%;">
<tbody>
<tr>
<td style="width: 100%;"><span style="color: #ee2323;"><b>명령어 'systemd-resolve' 을(를) 찾을 수 없습니다.</b></span> 그러나 다음을 통해설치할 수 있습니다:<br />apt install systemd<br />관리자에게 문의하세요.</td>
</tr>
</tbody>
</table>
<p>&nbsp;</p>
<p>apt install systemd 명령으로 설치할 수 있다고 하여 시도해보았습니다.</p>
<pre class="bash" id="code_1662612694859"><code>$ sudo apt-get install systemd</code></pre>
<p>하지만 실제로 sudo apt-get install systemd 명령으로 systemd 패키지를 설치해보려고 하면 이미 설치되어 있다고 나옵니다.</p>
<table border="1" style="border-collapse: collapse; width: 100%;">
<tbody>
<tr>
<td style="width: 100%;"><span style="color: #ee2323;"><b>패키지 systemd는 이미 최신 버전입니다. (249.11-0ubuntu3.4).</b></span></td>
</tr>
</tbody>
</table>
<p>&nbsp;</p>
<h2>22.04에서는 "resolvectl status" 명령을 입력하면 됨</h2>
<p>22.04에서는 더 이상 "systemd-resolve" 명령을 지원하지 않습니다. 대신 "resolvectl status" 명령을 이용하시면 됩니다.</p>
<pre class="bash" id="code_1662612903734"><code>$ resolvectl status</code></pre>
<p>&nbsp;</p>
<p>관련 내용은 아래의 링크를 참고하시기 바랍니다.</p>
<figure contenteditable="false" id="og_1662612979145"><a href="https://askubuntu.com/questions/1409726/systemd-resolve-command-not-found-in-ubuntu-22-04-desktop" rel="noopener">
<div class="og-image">&nbsp;</div>
<div class="og-text">
<p class="og-title">systemd-resolve command not found in Ubuntu 22.04 desktop</p>
<p class="og-desc">Hi I am going through some tutorials. When I try to execute systemd-resolve --status in Ubuntu 22.04 desktop, system reports command not found. What am I doing wrong here? I tried running sudo apt-...</p>
<p class="og-host">askubuntu.com</p>
</div>
</a></figure>
<p>&nbsp;</p>
<p>이상입니다.</p>
<p>&nbsp;</p>
<p>&nbsp;</p>"
keywords:
crawler_version: "2.2"
images:
---

# 우분투 22.04에서 systemd-resolve 명령어를 찾을 수 없을 경우 문제 해결 방법

(본문 없음)