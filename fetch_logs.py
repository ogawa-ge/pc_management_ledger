import subprocess
import json

def clean_and_parse_json(raw_bytes):
    """
    標準出力に含まれる AWS CLI 独自の文字コード警告などのゴミを取り除き、
    純粋な JSON 部分だけをパースします。
    """
    text = raw_bytes.decode('utf-8', errors='ignore')
    
    # 最初の '{' から最後の '}' までの範囲を切り出す
    start_idx = text.find('{')
    end_idx = text.rfind('}') + 1
    
    if start_idx != -1 and end_idx > start_idx:
        json_str = text[start_idx:end_idx]
        return json.loads(json_str)
    
    raise ValueError("Valid JSON structure not found in the output")

def fetch():
    try:
        # 1. ログストリーム名を取得
        res = subprocess.run(
            ['aws', 'logs', 'describe-log-streams', '--log-group-name', '/aws/lambda/LambdaStack-ApiLambda91D2282D-iKsp92JDmJah', '--order-by', 'LastEventTime', '--descending', '--max-items', '1', '--no-cli-pager'],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        
        stream_data = clean_and_parse_json(res.stdout)
        stream_name = stream_data['logStreams'][0]['logStreamName']
        
        # 2. 最新のログイベントを取得
        res_events = subprocess.run(
            ['aws', 'logs', 'get-log-events', '--log-group-name', '/aws/lambda/LambdaStack-ApiLambda91D2282D-iKsp92JDmJah', '--log-stream-name', stream_name, '--no-cli-pager'],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        
        events_data = clean_and_parse_json(res_events.stdout)
        events = events_data.get('events', [])
        
        # 3. ログのメッセージをファイルに保存
        with open('error_logs_fresh20.txt', 'w', encoding='utf-8') as f:
            for ev in events[-40:]:
                f.write(ev['message'])
        print("Success! Fresh logs saved to error_logs_fresh20.txt")
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            with open('debug_stream.txt', 'wb') as f:
                f.write(res.stdout)
            with open('debug_events.txt', 'wb') as f:
                f.write(res_events.stdout)
        except Exception as write_err:
            print(f"Failed to write debug files: {write_err}")
        print(f"Error: {str(e)}")

if __name__ == '__main__':
    fetch()
