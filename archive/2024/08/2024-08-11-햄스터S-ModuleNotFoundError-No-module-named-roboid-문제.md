---
title: "[햄스터S] ModuleNotFoundError: No module named 'roboid' 문제 해결 방법 (Ubuntu Linux)"
url: "https://frankler.tistory.com/3789"
created_at: "2024-08-11T20:32:56+09:00"
event_dates:
  - "2024-08-11"
category: ""
tags:
---

# [햄스터S] ModuleNotFoundError: No module named 'roboid' 문제 해결 방법 (Ubuntu Linux)

<h2>문제의 상황</h2>
<p>&nbsp;</p>
<p>오랜만에 햄스터S 스크립트를 실행시켜보니 아래와 같이 'roboid' 패키지가 없다는 에러 메시지가 발생을 했습니다.</p>
<pre class="python" id="code_1723342172535"><code>$ ./follow_wall.py
Traceback (most recent call last):
  File "/home/parksejin/project/hamsters/./follow_wall.py", line 3, in &lt;module&gt;
    from roboid import *
ModuleNotFoundError: No module named 'roboid'</code></pre>
<p>&nbsp;</p>
<h2>1. roboid 모듈&nbsp; 설치</h2>
<p><span style="color: #ee2323;"><b>pip install -U roboid</b></span> 명령으로 패키지를 설치를 시도합니다.</p>
<p>예전에 낮은 버전의 파이썬3를 사용할 경우 문제 없이 동작합니다.</p>
<p>&nbsp;</p>
<pre class="bash" id="code_1723342442309"><code>$ pip install -U roboid
error: externally-managed-environment

&times; This environment is externally managed
╰─&gt; To install Python packages system-wide, try apt install
    python3-xyz, where xyz is the package you are trying to
    install.
    
    If you wish to install a non-Debian-packaged Python package,
    create a virtual environment using python3 -m venv path/to/venv.
    Then use path/to/venv/bin/python and path/to/venv/bin/pip. Make
    sure you have python3-full installed.
    
    If you wish to install a non-Debian packaged Python application,
    it may be easiest to use pipx install xyz, which will manage a
    virtual environment for you. Make sure you have pipx installed.
    
    See /usr/share/doc/python3.12/README.venv for more information.

note: If you believe this is a mistake, please contact your Python installation or OS distribution provider. You can override this, at the risk of breaking your Python installation or OS, by passing --break-system-packages.
hint: See PEP 668 for the detailed specification.</code></pre>
<p>&nbsp;</p>
<p>제 경우는 파이썬 3.12를 사용하고 있어서 설치 에러가 발생했습니다.</p>
<p>이 때는 venv를 이용하면 됩니다.</p>
<p>&nbsp;</p>
<h2>2. venv를 이용하여 roboid 모듈 설치</h2>
<p>$ <span style="color: #ee2323;"><b>python3 -m venv hamster</b></span> 명령을 이용해서 가상 환경을 만듭니다.</p>
<pre class="bash" id="code_1723342684769"><code>$ python3 -m venv hamster
The virtual environment was not created successfully because ensurepip is not
available.  On Debian/Ubuntu systems, you need to install the python3-venv
package using the following command.

    apt install python3.12-venv

You may need to use sudo with that command.  After installing the python3-venv
package, recreate your virtual environment.

Failing command: /home/myaccount/project/hamsters/hamster/bin/python3</code></pre>
<p>&nbsp;</p>
<p>venv를 사용하기 위해서는 python3.12-venv 패키지를 설치해야 합니다.</p>
<p>$ <span style="color: #ee2323;"><b>sudo apt-get install python3.12-venv</b></span> 명령으로 패키지를 설치해줍니다.</p>
<p>&nbsp;</p>
<p>$ <span style="color: #ee2323;"><b>source hamster/bin/activate</b></span> 명령으로 가상 환경을 activate 해줍니다.</p>
<p>&nbsp;</p>
<p>가상 환경에서 pip 명령으로 roboid 모듈 설치</p>
<pre class="bash" id="code_1723342969797"><code>$ pip3 install roboid
Collecting roboid
  Downloading roboid-1.6.4-py3-none-any.whl.metadata (608 bytes)
Collecting pyserial (from roboid)
  Downloading pyserial-3.5-py2.py3-none-any.whl.metadata (1.6 kB)
Downloading roboid-1.6.4-py3-none-any.whl (92 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 92.1/92.1 kB 3.3 MB/s eta 0:00:00
Downloading pyserial-3.5-py2.py3-none-any.whl (90 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 90.6/90.6 kB 4.0 MB/s eta 0:00:00
Installing collected packages: pyserial, roboid
Successfully installed pyserial-3.5 roboid-1.6.4</code></pre>
<p>&nbsp;</p>
<p>&nbsp;</p>
<h2>3. roboid 모듈 설치 완료 확인</h2>
<p>다시 스크립트를 실행해보면 roboid 모듈에 제대로 설치되어 있는 것을 확인할 수 있습니다.</p>
<pre class="bash" id="code_1723343123566"><code>$ ./follow_wall.py 
HamsterS[0] No available USB to BLE bridge</code></pre>
<p>&nbsp;</p>
<p>이상입니다.</p>