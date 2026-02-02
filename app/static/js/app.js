/*
Design原則準拠: 直接操作、即時反応、取り消し可能
65. 0.1秒以内に反応を返す
*/

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('submitForm');
    const submitBtn = document.getElementById('submitBtn');
    const errorMessage = document.getElementById('errorMessage');
    const successModal = document.getElementById('successModal');

    // Design原則: 8. 直接操作 - 即時反応
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Design原則: 65. 0.1秒以内に反応
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="loading"></span> 処理中...';
        errorMessage.style.display = 'none';

        const formData = {
            video_url: document.getElementById('videoUrl').value,
            src_lang: document.getElementById('srcLang').value,
            tgt_lang: document.getElementById('tgtLang').value,
            email: document.getElementById('email').value
        };

        try {
            const response = await fetch('/api/v1/jobs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || '投稿に失敗しました');
            }

            // Design原則: 66. 操作の近くでフィードバック
            showSuccessModal(data);
            form.reset();

        } catch (error) {
            // Design原則: 55. エラー表示は建設的に
            errorMessage.textContent = error.message;
            errorMessage.style.display = 'block';
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = '処理を開始';
        }
    });

    function showSuccessModal(data) {
        document.getElementById('modalJobId').textContent = data.job_id;
        document.getElementById('modalStatusLink').href = `/status/${data.job_id}`;
        successModal.style.display = 'flex';

        // Design原則: 60. エスケープハッチ
        successModal.addEventListener('click', (e) => {
            if (e.target === successModal) {
                successModal.style.display = 'none';
            }
        });
    }

    // Design原則: 13. コンストレイント（リアルタイムバリデーション）
    const urlInput = document.getElementById('videoUrl');
    urlInput.addEventListener('blur', () => {
        const value = urlInput.value;
        const isYouTube = /youtube\.com|youtu\.be/.test(value);
        
        if (value && !isYouTube) {
            urlInput.setCustomValidity('YouTube URLを入力してください');
        } else {
            urlInput.setCustomValidity('');
        }
    });

    // Design原則: 39. 整合性を損なう操作を求めない
    const srcLang = document.getElementById('srcLang');
    const tgtLang = document.getElementById('tgtLang');
    
    srcLang.addEventListener('change', () => {
        if (srcLang.value === tgtLang.value && tgtLang.value) {
            tgtLang.value = '';
            alert('元の言語と翻訳先の言語は異なる必要があります');
        }
    });

    tgtLang.addEventListener('change', () => {
        if (srcLang.value === tgtLang.value && srcLang.value) {
            tgtLang.value = '';
            alert('元の言語と翻訳先の言語は異なる必要があります');
        }
    });
});
