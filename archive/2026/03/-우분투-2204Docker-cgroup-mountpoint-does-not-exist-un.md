---
title: "[우분투 22.04][Docker] cgroup mountpoint does not exist: unknown 해결 방법"
url: "https://worldclassproduct.tistory.com/entry/%EC%9A%B0%EB%B6%84%ED%88%AC-2204Docker-cgroup-mountpoint-does-not-exist-unknown-%ED%95%B4%EA%B2%B0-%EB%B0%A9%EB%B2%95"
created_at: "Tue, 13 Sep 2022 11:24:37 +0900"
event_dates:
category: ""
tags:
comments: "<p><figure class="imageblock alignCenter"><span><img height="1036" src="https://blog.kakaocdn.net/dn/ZHjbc/btrL0TUpVEt/wLv4hXCvplIhOwKVs04I7k/img.jpg" width="1109" /></span></figure>
</p>
<p>&nbsp;</p>
<p>최근에 우분투 리눅스를 22.04로 업그레이드한 이후에 여러 가지 문제점들이 발생하고 있습니다. 그중에서도 기존에는 잘 실행되던 도커 이미지가 제대로 실행되지 못하는 문제가 발생했습니다. 본 페이지에서는 우분투 리눅스를 22.04로 업그레이드한 이후에 도커 실행 시에 "cgroups: cgroup mountpoint does not exist: unknown"와 같은 에러 메시지가 발생할 때 조치하는 방법에 대해서 설명하고자 합니다.</p>
<p>&nbsp;</p>
<hr contenteditable="false" />
<h2>1. 문제의 현상 기술</h2>
<p>기존에 우분투 20.04에서는 도커 이미지를 실행하는데 전혀 문제가 없었습니다. 최근에 우분투 리눅스를 20.04에서 22.04로 업그레이드한 이후에 갑자기 이런 문제가 발생을 했습니다.</p>
<p>도커 이미지를 실행시에 <span style="color: #ee2323;"><b>"cgroups: cgroup mountpoint does not exist: unknown"</b></span>와 같은 에러 메시지가 발생하고 있습니다.</p>
<p>&nbsp;</p>
<h2>2. 임시 조치 방법</h2>
<p>구글링을 해보면 아래의 명령을 수행해주면 문제가 해결된다고 합니다.</p>
<pre class="awk" id="code_1663031739800"><code>$ sudo mkdir /sys/fs/cgroup/systemd</code></pre>
<p>&nbsp;</p>
<p>하지만 제 경우는 위의 명령을 수행해도 여전히 문제가 발생해서 아래의 명령을 추가로 실행해주었습니다.</p>
<pre class="awk" id="code_1663031739801"><code>$ sudo mount -t cgroup -o none,name=systemd cgroup /sys/fs/cgroup/systemd</code></pre>
<p>&nbsp;</p>
<p>위와 같이 조치하면 일단은 도커 이미지가 제대로 실행되는 것처럼 보입니다. 하지만, 재부팅을 하면 해당 문제가 다시 발생하게 됩니다. 물론, 부팅 시에 자동으로 위의 명령들이 실행될 수 있도록 스크립트를 구성하는 것도 하나의 방법이겠습니다만 workaround라는 느낌을 지울 수 없습니다. </p>
<p>&nbsp;</p>
<h2>4. 영구 해결 방법</h2>
<p>해당 문제는 우분투 리눅스와 도커의 버전이 서로 맞지 않아서 발생하는 문제입니다. 우분투 리눅스는 최신인데, 도커는 예전 버전이기 때문입니다. 따라서, <span style="color: #006dd7;"><b>도커를 삭제하고 재설치하면 이 문제를 깨끗하게 해결할 수 있습니다.</b></span> 아래의 글은 도커를 깨끗하게 제거하고 다시 설치하는 방법에 대해서 설명되어 있습니다.</p>
<figure contenteditable="false" id="og_1663041293947"><a href="https://worldclassproduct.tistory.com/entry/%EC%9A%B0%EB%B6%84%ED%88%AC-2204-%EB%8F%84%EC%BB%A4-%EC%84%A4%EC%B9%98%ED%95%98%EB%8A%94-%EB%B0%A9%EB%B2%95-Ubuntu-2204-Docker-Install" rel="noopener" target="_blank">
<div class="og-image">&nbsp;</div>
<div class="og-text">
<p class="og-title">[우분투 22.04] 도커 설치하는 방법 (Ubuntu 22.04 Docker Install)</p>
<p class="og-desc">필자는 최근에 우분투 리눅스 20.04에서 22.04로 업그레이드를 했습니다. 우분투 리눅스를 업그레이드한 이후에 여러 가지 문제들이 발생했습니다. 도어 관련 에러도 그중의 하나였습니다. 참고로</p>
<p class="og-host">worldclassproduct.tistory.com</p>
</div>
</a></figure>
<p>&nbsp;</p>
<h2>3. 결론</h2>
<p>Docker에서 "cgroups: cgroup mountpoint does not exist: unknown"와 같은 에러 메시지가 발생하면 아래의 2개의 명령을 수행해주면 됩니다.</p>
<pre class="awk" id="code_1663031960177"><code>$ sudo mkdir /sys/fs/cgroup/systemd
$ sudo mount -t cgroup -o none,name=systemd cgroup /sys/fs/cgroup/systemd</code></pre>
<p>&nbsp;</p>
<p>&nbsp;</p>
<h2>관련 링크</h2>
<p>제가 도움을 받은 링크는 아래와 같습니다.</p>
<figure contenteditable="false" id="og_1663031940689"><a href="https://bigdata-etl.com/docker-cgroup-mountpoint-does-not-exist-unknown/" rel="noopener" target="_blank">
<div class="og-image">&nbsp;</div>
<div class="og-text">
<p class="og-title">[SOLVED] Docker: Error Response From Daemon: Cgroups: Cgroup Mountpoint Does Not Exist: Unknown - 1 Min Great Solution! Cgroup M</p>
<p class="og-desc">29 June 2022 &mdash; Open terminal and paste the following command. It will fix the issue: cgroup mountpoint does not exist which you have which is related</p>
<p class="og-host">bigdata-etl.com</p>
</div>
</a></figure>
<p>&nbsp;</p>
<p>만약 "cgroups: cannot found cgroup mount destination: unknown"와 같은 에러가 발생한다면 아래의 글을 참고하시기 바랍니다.</p>
<figure contenteditable="false" id="og_1663032264512"><a href="https://worldclassproduct.tistory.com/entry/%EC%9A%B0%EB%B6%84%ED%88%ACDocker-cgroups-cannot-found-cgroup-mount-destination-unknown-%EC%97%90%EB%9F%AC-%EC%A1%B0%EC%B9%98-%EB%B0%A9%EB%B2%95" rel="noopener" target="_blank">
<div class="og-image">&nbsp;</div>
<div class="og-text">
<p class="og-title">[우분투/Docker] cgroups: cannot found cgroup mount destination: unknown 에러 조치 방법</p>
<p class="og-desc">최근에 우분투 리눅스를 22.04로 업그레이드한 이후에 여러가지 문제점들이 발생하고 있습니다. 그 중에서도 기존에는 잘 실행되던 도커 이미지가 제대로 실행되지 못하는 문제가 발생했습니다.</p>
<p class="og-host">worldclassproduct.tistory.com</p>
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

# [우분투 22.04][Docker] cgroup mountpoint does not exist: unknown 해결 방법

(본문 없음)