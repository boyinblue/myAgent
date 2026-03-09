import argparse
import sys
import io
import platform

# Windows에서 UTF-8 이모지 출력을 위한 설정
if platform.system() == 'Windows':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from email_agent.config import load_settings
from email_agent.imap_client import DaumImapClient
from email_agent.unsubscribe import execute_action
from email_agent.workflow import summarize_by_sender
from email_agent.whitelist import Whitelist


def interactive_loop(summaries, dry_run: bool, whitelist: Whitelist):
    """순위별로 Y/N으로 수신거부 여부를 물어보는 방식"""
    for idx, summary in enumerate(summaries, start=1):
        display_name = summary.sender_name or "(no-name)"
        action_count = len(summary.actions)
        
        print(f"\n[{idx}/{len(summaries)}] {summary.count:>3}건 | {summary.sender_email} | {display_name}")
        if summary.sample_subject:
            print(f"     샘플: {summary.sample_subject[:80]}")
        
        if action_count > 0:
            print(f"     수신거부 후보: {action_count}개")
            for i, action in enumerate(summary.actions[:3], start=1):
                print(f"       {i}. {action.kind} -> {action.value[:60]}")
            if action_count > 3:
                print(f"       ... 외 {action_count - 3}개")
        else:
            print("     수신거부 후보 없음")
        
        # Y/N/S 입력 받기
        while True:
            choice = input("\n수신거부 하시겠습니까? (Y=실행/N=화이트리스트/s=건너뛰기/q=종료): ").strip().upper()
            if choice in ("Q", "QUIT", "EXIT"):
                print("종료합니다.")
                return
            elif choice == "Y":
                # 수신거부 실행
                if not summary.actions:
                    print("❌ 수신거부 후보가 없습니다.")
                    break
                
                # 첫 번째 action 실행 (또는 사용자가 선택하도록 할 수도 있음)
                action = summary.actions[0]
                print(f"📧 실행: {action.kind} -> {action.value}")
                confirm = input("   정말 실행할까요? (y/N): ").strip().lower()
                if confirm == "y":
                    result = execute_action(action, dry_run=dry_run)
                    print(f"   결과: {result}")
                else:
                    print("   취소되었습니다.")
                break
            elif choice == "N":
                # 화이트리스트에 추가
                whitelist.add(summary.sender_email)
                print(f"✅ [{summary.sender_email}] 화이트리스트에 추가됨")
                break
            elif choice == "S":
                print(f"⏭️ [{summary.sender_email}] 건너뜀 (화이트리스트 추가 안 함)")
                break
            else:
                print("Y, N, S, Q 중 하나를 입력하세요.")
    
    print(f"\n✅ 모든 발신자 처리 완료 (화이트리스트: {len(whitelist)}개)")



def main():
    parser = argparse.ArgumentParser(description="Daum mail unsubscribe assistant")
    parser.add_argument("--limit", type=int, default=300, help="Number of recent emails to fetch per mailbox")
    parser.add_argument("--include-spam", action="store_true", help="Include spam mailbox")
    parser.add_argument("--dry-run", action="store_true", help="Test mode - do not actually execute unsubscribe")
    args = parser.parse_args()

    try:
        settings = load_settings()
    except Exception as exc:
        print(f"설정 로드 실패: {exc}")
        return

    dry_run = args.dry_run
    
    # 화이트리스트 로드
    whitelist = Whitelist()
    if len(whitelist) > 0:
        print(f"📋 화이트리스트: {len(whitelist)}개 발신자")

    print(f"\n🔌 IMAP 서버 접속 중... (imap.daum.net)")
    try:
        with DaumImapClient(settings) as client:
            print(f"📥 메일 가져오는 중... (최대 {args.limit}건)")
            records = client.fetch_recent(settings.inbox_name, limit=args.limit)
            if args.include_spam:
                print(f"📥 스팸함 가져오는 중... (최대 {args.limit}건)")
                records.extend(client.fetch_recent(settings.spam_name, limit=args.limit))
    except Exception as exc:
        print("IMAP 접속 실패")
        print(f"- 상세: {exc}")
        print("- 점검: DAUM_APP_PASSWORD(앱 비밀번호), DAUM_EMAIL 형식(id@daum.net), IMAP 호스트")
        return

    if not records:
        print("메일을 찾지 못했습니다.")
        return

    print(f"✅ {len(records)}건의 메일 로드 완료")
    print(f"📊 발신자별 집계 중...")
    summaries = summarize_by_sender(records, whitelist=whitelist)
    if not summaries:
        print("집계 가능한 발신자가 없습니다. (모두 화이트리스트에 있거나 발신자 없음)")
        return

    print(f"\n총 {len(summaries)}명의 발신자 (화이트리스트 제외)")
    print(f"Mode: {'🔍 DRY-RUN (테스트)' if dry_run else '⚡ APPLY (실제 실행)'}")
    interactive_loop(summaries[:30], dry_run=dry_run, whitelist=whitelist)


if __name__ == "__main__":
    main()
