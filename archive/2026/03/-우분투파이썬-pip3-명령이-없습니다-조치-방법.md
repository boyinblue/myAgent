---
title: "[우분투][파이썬] pip3: 명령이 없습니다 조치 방법"
url: "https://worldclassproduct.tistory.com/entry/%EC%9A%B0%EB%B6%84%ED%88%AC%ED%8C%8C%EC%9D%B4%EC%8D%AC-pip3-%EB%AA%85%EB%A0%B9%EC%9D%B4-%EC%97%86%EC%8A%B5%EB%8B%88%EB%8B%A4-%EC%A1%B0%EC%B9%98-%EB%B0%A9%EB%B2%95"
created_at: "Tue, 27 Sep 2022 00:05:33 +0900"
event_dates:
category: ""
tags:
comments: "<p><figure class="imageblock alignCenter"><span><img height="725" src="https://blog.kakaocdn.net/dn/vwl3L/btrM9R1Y0d1/MVoBOweDJqU00LrzlRtvz1/img.png" width="786" /></span></figure>
</p>
<p>새로운 라즈베리파이에 기존에 만들어놓은 서비스를 돌리려고 하다 보니 이런저런 에러가 발생하고 있습니다. 새로운 서버를 구성하는 일은 자주 없기 때문에 필요한 패키지들을 추가로 설치하는 일이 빈번하지는 않지만, 가끔 하다 보니 방법을 잊어버릴 때가 많이 있습니다.&nbsp;</p>
<p>&nbsp;</p>
<h2>문제의 현상</h2>
<p>파이썬에서 새로운 모듈을 설치할 때 pip3 명령을 자주 사용합니다.&nbsp;</p>
<pre class="bash" id="code_1664204324869"><code>$ sudo pip3 install gtts</code></pre>
<p>&nbsp;</p>
<p>하지만 pip3 패키지가 설치되어 있지 않은 경우에 아래와 같은 에러 메시지를 토해냅니다.&nbsp;</p>
<table border="1" style="border-collapse: collapse; width: 100%;">
<tbody>
<tr>
<td style="width: 100%;"><span style="color: #ee2323;"><b>sudo:&nbsp;pip3:&nbsp;명령이&nbsp;없습니다</b></span></td>
</tr>
</tbody>
</table>
<h2>&nbsp;</h2>
<p>보통 우분투에서는 없는 명령어를 입력할 경우에 어떤 패키지를 설치해야 되는지 친절하게 알려주는 편입니다.&nbsp;</p>
<p>예를 들면, hub 라는 명령을 입력했는데 hub 패키지가 설치되어 있지 않다면, 아래와 같이 어떤 패키지를 설치해야 되는지 친절하게 설명해줍니다.</p>
<table border="1" style="border-collapse: collapse; width: 100%;">
<tbody>
<tr>
<td style="width: 100%;">$&nbsp;hub<br /><span style="color: #ee2323;"><b>명령어&nbsp;'hub'&nbsp;을(를)&nbsp;찾을&nbsp;수&nbsp;없습니다.</b></span>&nbsp;그러나&nbsp;다음을&nbsp;통해&nbsp;설치할&nbsp;수&nbsp;있습니다:<br /><span style="color: #006dd7;"><b>sudo&nbsp;apt&nbsp;install&nbsp;hub</b></span></td>
</tr>
</tbody>
</table>
<p>하지만 pip3에 대해서는 어떤 패키지를 설치해야 되는지 알려주지 않습니다.&nbsp;</p>
<p>&nbsp;</p>
<h2>초간단 조치 방법</h2>
<p>이 때는 python3-pip 패키지를 설치하면 됩니다. 아래의 명령으로 python3-pip 패키지를 설치합니다.&nbsp;</p>
<pre class="bash" id="code_1664204579441"><code>$ sudo apt-get install python3-pip</code></pre>
<p>&nbsp;</p>
<p>패키지 설치 이후에 pip3 명령을 입력하면 정상적으로 실행되는 것을 확인하실 수 있습니다.&nbsp;</p>
<pre class="bash" id="code_1664204678661"><code>$ sudo pip3 install gtts</code></pre>
<p>&nbsp;</p>
<p>&nbsp;</p>
<p>이상입니다.&nbsp;</p>
<p>&nbsp;</p>
<p>&nbsp;</p>"
keywords:
crawler_version: "2.2"
images:
---

# [우분투][파이썬] pip3: 명령이 없습니다 조치 방법

(본문 없음)