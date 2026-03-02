---
title: "ModuleNotFoundError: No module named 'speech_recognition' 해결 방법"
url: "https://worldclassproduct.tistory.com/entry/ModuleNotFoundError-No-module-named-speechrecognition-%ED%95%B4%EA%B2%B0-%EB%B0%A9%EB%B2%95"
created_at: "Tue, 27 Sep 2022 00:53:40 +0900"
event_dates:
category: ""
tags:
comments: "<p><figure class="imageblock alignCenter"><span><img height="725" src="https://blog.kakaocdn.net/dn/59Q8G/btrM36tlCae/dkAVneI3kGrtH2C1K4dVAK/img.png" width="786" /></span></figure>
</p>
<p>예전에 잘 만들어 놓은 파이썬 스크립트를 새로 셋업 한 PC에서 실행시켜보면 여러 가지 에러가 발생을 합니다. 필요한 파이썬 모듈을 찾지 못해서 발생한 문제들이 대부분입니다.&nbsp;</p>
<p>&nbsp;</p>
<h2>문제의 현상</h2>
<p>파이썬 스크립트 실행 시에 아래와 같은 에러가 발생함.</p>
<table border="1" style="border-collapse: collapse; width: 100%;">
<tbody>
<tr>
<td style="width: 100%;"><span style="color: #ee2323;"><b>ModuleNotFoundError: No module named 'speech_recognition'</b></span></td>
</tr>
</tbody>
</table>
<p>&nbsp;</p>
<h2>조치방법</h2>
<p>pip3 명령으로 SpeechRecognition 모듈을 설치하면 됩니다.</p>
<h3>명령어</h3>
<pre class="python" id="code_1664207433005"><code>$ sudo pip3 install SpeechRecognition</code></pre>
<p>&nbsp;</p>
<h3>실행 결과</h3>
<table border="1" style="border-collapse: collapse; width: 100%;">
<tbody>
<tr>
<td style="width: 100%;">$&nbsp;sudo&nbsp;pip3&nbsp;install&nbsp;SpeechRecognition<br />[sudo]&nbsp;parksejin&nbsp;암호:&nbsp;<br />Collecting&nbsp;SpeechRecognition<br />&nbsp;&nbsp;Downloading&nbsp;SpeechRecognition-3.8.1-py2.py3-none-any.whl&nbsp;(32.8&nbsp;MB)<br />&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━&nbsp;32.8/32.8&nbsp;MB&nbsp;2.0&nbsp;MB/s&nbsp;eta&nbsp;0:00:00<br />Installing&nbsp;collected&nbsp;packages:&nbsp;SpeechRecognition<br />Successfully&nbsp;installed&nbsp;SpeechRecognition-3.8.1<br />WARNING:&nbsp;Running&nbsp;pip&nbsp;as&nbsp;the&nbsp;'root'&nbsp;user&nbsp;can&nbsp;result&nbsp;in&nbsp;broken&nbsp;permissions&nbsp;and&nbsp;conflicting&nbsp;behaviour&nbsp;with&nbsp;the&nbsp;system&nbsp;package&nbsp;manager.&nbsp;It&nbsp;is&nbsp;recommended&nbsp;to&nbsp;use&nbsp;a&nbsp;virtual&nbsp;environment&nbsp;instead:&nbsp;https://pip.pypa.io/warnings/venv</td>
</tr>
</tbody>
</table>
<p>&nbsp;</p>
<h2>pip3 명령이 없습니다?</h2>
<p>만약 pip3 명령이 없다는 에러가 발생할 경우 pip3 패키지를 설치하면 됩니다.&nbsp;</p>
<figure contenteditable="false" id="og_1664207516371"><a href="https://worldclassproduct.tistory.com/entry/%EC%9A%B0%EB%B6%84%ED%88%AC%ED%8C%8C%EC%9D%B4%EC%8D%AC-pip3-%EB%AA%85%EB%A0%B9%EC%9D%B4-%EC%97%86%EC%8A%B5%EB%8B%88%EB%8B%A4-%EC%A1%B0%EC%B9%98-%EB%B0%A9%EB%B2%95" rel="noopener">
<div class="og-image">&nbsp;</div>
<div class="og-text">
<p class="og-title">[우분투][파이썬] pip3: 명령이 없습니다 조치 방법</p>
<p class="og-desc">새로운 라즈베리파이에 기존에 만들어놓은 서비스를 돌리려고 하다 보니 이런저런 에러가 발생하고 있습니다. 새로운 서버를 구성하는 일은 자주 없기 때문에 필요한 패키지들을 추가로 설치</p>
<p class="og-host">worldclassproduct.tistory.com</p>
</div>
</a></figure>
<p>&nbsp;</p>
<p>이상입니다.&nbsp;</p>
<p>&nbsp;</p>"
keywords:
crawler_version: "2.2"
images:
---

# ModuleNotFoundError: No module named 'speech_recognition' 해결 방법

(본문 없음)