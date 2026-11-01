"""
Фоновый IPC-воркер для мгновенного RVC преобразования голоса на GPU.
Библиотечные логи изолированы в stderr, а протокол обмена работает через дублированный чистый дескриптор stdout.
"""

import sys
import json
import os
import time

def main():
    if len(sys.argv) < 3:
        sys.stderr.write("Usage: rvc_worker.py <model_path> <index_path> [version] [device]\n")
        return

    model_path = sys.argv[1]
    index_path = sys.argv[2]
    version = sys.argv[3] if len(sys.argv) > 3 else "v1"
    device = sys.argv[4] if len(sys.argv) > 4 else "cuda:0"

    # Создаём чистый канал для JSON-ответов
    pipe_out = os.fdopen(os.dup(1), "w")
    # Перенаправляем стандартный sys.stdout в sys.stderr, чтобы fairseq не засорял протокол
    sys.stdout = sys.stderr

    def send_json(data):
        pipe_out.write(json.dumps(data) + "\n")
        pipe_out.flush()

    try:
        from rvc_python.infer import RVCInference
        rvc = RVCInference(
            device=device,
            model_path=model_path,
            index_path=index_path if os.path.exists(index_path) else None,
            version=version
        )
        send_json({"status": "ready"})
    except Exception as e:
        send_json({"status": "error", "message": str(e)})
        return

    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line.strip())
            action = req.get("action")
            if action == "exit":
                break
            elif action == "convert":
                input_path = req["input_path"]
                output_path = req["output_path"]
                index_rate = float(req.get("index_rate", 0.32))
                filter_radius = int(req.get("filter_radius", 7))
                rms_mix_rate = float(req.get("rms_mix_rate", 0.30))
                protect = float(req.get("protect", 0.50))
                f0up_key = int(req.get("f0up_key", 0))
                f0method = req.get("f0method", "rmvpe")

                t0 = time.time()
                rvc.set_params(
                    f0method=f0method,
                    f0up_key=f0up_key,
                    index_rate=index_rate,
                    filter_radius=filter_radius,
                    rms_mix_rate=rms_mix_rate,
                    protect=protect
                )
                rvc.infer_file(input_path, output_path)
                elapsed = time.time() - t0
                send_json({"status": "ok", "elapsed_sec": round(elapsed, 3)})
            else:
                send_json({"status": "error", "message": f"Unknown action: {action}"})
        except Exception as e:
            send_json({"status": "error", "message": str(e)})

if __name__ == "__main__":
    main()
