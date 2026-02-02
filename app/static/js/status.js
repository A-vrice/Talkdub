/*
Design原則: 19. タスクコヒーレンス - 前回の行動を手がかりに支援
*/

const jobId = window.location.pathname.split('/').pop();
let pollInterval;

// Design原則: 65. 進捗などで補う（自動ポーリング）
async function fetchStatus() {
    try {
        const response = await fetch(`/api/v1/jobs/${jobId}/status`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail);
        }

        updateUI(data);

        // Design原則: 90. UIをロックしない
        if (data.status === 'COMPLETED' || data.status === 'FAILED') {
            clearInterval(pollInterval);
        }

    } catch (error) {
        document.getElementById('errorSection').style.display = 'block';
        document.getElementById('errorText').textContent = error.message;
        clearInterval(pollInterval);
    }
}

function updateUI(data) {
    // Design原則: 25. 状態を常時・視覚的・即時に示す
    document.getElementById('jobId').textContent = data.job_id;
    document.getElementById('currentPhase').textContent = data.current_phase || '待機中';
    document.getElementById('createdAt').textContent = new Date(data.created_at).toLocaleString('ja-JP');
    document.getElementById('eta').textContent = new Date(data.estimated_completion).toLocaleString('ja-JP');

    // ステータスバッジ
    const badge = document.getElementById('statusBadge');
    badge.textContent = data.status;
    badge.className = `status-badge status-${data.status.toLowerCase()}`;

    // 進捗バー
    const percent = data.progress.percent || 0;
    document.getElementById('progressFill').style.width = `${percent}%`;
    document.getElementById('progressText').textContent = 
        `${data.progress.completed_segments || 0} / ${data.progress.total_segments || 0} セグメント完了 (${percent.toFixed(1)}%)`;

    // ダウンロードボタン表示
    if (data.download_available) {
        document.getElementById('downloadSection').style.display = 'block';
    }

    // エラー表示
    if (data.error) {
        document.getElementById('errorSection').style.display = 'block';
        document.getElementById('errorText').textContent = data.error;
    }
}

// PIN認証モーダル処理
document.getElementById('downloadBtn')?.addEventListener('click', () => {
    document.getElementById('pinModal').style.display = 'flex';
    document.querySelectorAll('.pin-digit')[0].focus();
});

// Design原則: 8. 直接操作 - 自動フォーカス移動
const pinInputs = document.querySelectorAll('.pin-digit');
pinInputs.forEach((input, index) => {
    input.addEventListener('input', (e) => {
        if (e.target.value.length === 1 && index < pinInputs.length - 1) {
            pinInputs[index + 1].focus();
        }
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && !e.target.value && index > 0) {
            pinInputs[index - 1].focus();
        }
    });
});

document.getElementById('pinSubmitBtn')?.addEventListener('click', async () => {
    const pin = Array.from(pinInputs).map(input => input.value).join('');
    
    if (pin.length !== 6) {
        document.getElementById('pinError').textContent = '6桁のPINコードを入力してください';
        document.getElementById('pinError').style.display = 'block';
        return;
    }

    try {
        const response = await fetch(`/api/v1/jobs/${jobId}/download`, {
            headers: {
                'X-PIN': pin
            }
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail);
        }

        // Design原則: 57. 黙って実行する
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `dub_${jobId}.zip`;
        a.click();

        document.getElementById('pinModal').style.display = 'none';

    } catch (error) {
        document.getElementById('pinError').textContent = error.message;
        document.getElementById('pinError').style.display = 'block';
    }
});

document.getElementById('pinCancelBtn')?.addEventListener('click', () => {
    document.getElementById('pinModal').style.display = 'none';
});

// 初回取得 & ポーリング開始
fetchStatus();
pollInterval = setInterval(fetchStatus, 10000); // 10秒ごと
