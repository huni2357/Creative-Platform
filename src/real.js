document.addEventListener('DOMContentLoaded', () => {
    const scrollContainer = document.getElementById('main-scroll-container');
    const sections = document.querySelectorAll('.snap-section');
    const navLinks = document.querySelectorAll('.header-nav-link');
    const mainHeader = document.getElementById('main-header');
    const orbStickyContainer = document.getElementById('orb-sticky-container');

    const phqScoreEl = document.getElementById('phqScore');
    const phqRiskLevelEl = document.getElementById('phqRiskLevel');
    const phqRiskContainer = document.getElementById('phqRiskContainer');
    const todayStatusMicrocopy = document.getElementById('todayStatusMicrocopy');
    const guideCardsContainer = document.getElementById('guideCards');

    let predictedScore = 4;

    const detailView = document.getElementById('detail-view');
    const detailCard = document.getElementById('detail-card');
    const detailContent = document.getElementById('detail-content');
    const closeDetailBtn = document.getElementById('close-detail-btn');
    const detailTitleEl = document.getElementById('detail-title');
    const detailInsightsEl = document.getElementById('detail-insights');
    const detailChartCanvas = document.getElementById('detail-chart');
    let detailChart;
    let originCardRect = null;

    const detailMockData = {
        positivity: {
            title: "긍정적 콘텐츠 소비 분석",
            insights: "<p>이번 주 <strong>긍정적 콘텐츠 소비 비율은 72%</strong>입니다. 긍정적인 정보를 꾸준히 접하는 것은 스트레스 감소에 큰 도움이 됩니다.</p>",
            chartData: {
                type: 'line',
                labels: ['월', '화', '수', '목', '금', '토', '일'],
                values: [65, 68, 62, 70, 75, 80, 78]
            }
        },
        activity: {
            title: "주요 활동 패턴 분석",
            insights: "<p>주요 활동 시간대는 <strong>오후 9시에서 11시 사이</strong>에 집중되어 있습니다. 건강한 수면 패턴을 유지하고 있습니다.</p>",
            chartData: {
                type: 'bar',
                labels: ['오전', '오후', '저녁', '밤', '새벽'],
                values: [15, 30, 45, 10, 0]
            }
        },
        balance: {
            title: "디지털-현실 균형 분석",
            insights: "<p>이번 주 <strong>총 사용 시간은 24.5시간</strong>으로, 지난주보다 15% 감소했습니다. 훌륭한 균형 감각입니다!</p>",
            chartData: {
                type: 'line',
                labels: ['4주전', '3주전', '2주전', '지난주', '이번주'],
                values: [32, 30, 29, 28, 24.5]
            }
        }
    };

    const guideData = {
        low: {
            microcopy: "좋은 흐름이에요. 오늘도 가볍게 이어가요.",
            subtitle: "요즘의 균형이 참 좋아요. 이 흐름을 조용히 이어가 볼까요?",
            cards: [{
                icon: "🌿",
                title: "오늘의 안부 묻기",
                content: "스스로에게 ‘오늘 어땠어?’ 하고 다정히 물어봐요."
            }, {
                icon: "✨",
                title: "작은 루틴 한 줌",
                content: "지금 잘 하고 있는 습관 1–2가지만 적어두고, 오늘도 가볍게 이어가요."
            }, {
                icon: "☕",
                title: "짧은 숨 고르기",
                content: "따뜻한 차 한 잔이나 3번의 깊은 호흡처럼, 작은 쉼이 하루를 부드럽게 만들어줘요."
            }]
        },
        medium: {
            microcopy: "작은 조절로 숨 쉴 틈을 열어볼게요.",
            subtitle: "조금 지친 마음이 느껴져요. 무리 없이 편안함을 다시 채워볼게요.",
            cards: [{
                icon: "🚶",
                title: "10분 햇살 산책",
                content: "잠깐이라도 바깥 공기를 마셔요."
            }, {
                icon: "🌙",
                title: "포근한 밤 준비",
                content: "잠들기 30분 전, 화면을 내려두고 조용한 음악이나 짧은 독서로 마음을 누그러뜨려요."
            }, {
                icon: "📝",
                title: "마음 내려놓기 메모",
                content: "걱정 1가지를 적고, 지금 할 수 있는 아주 작은 다음 한 걸음을 곁들여 봐요."
            }]
        },
        high: {
            microcopy: "혼자 버티지 않아도 괜찮아요. 연결이 힘이 됩니다.",
            subtitle: "지금은 연결이 힘이 될 때예요. 혼자서 다 헤아리지 않아도 괜찮아요.",
            cards: [{
                icon: "💬",
                title: "가벼운 상담 시작",
                content: "부담 없이 1회기만 예약해도 좋아요.",
                link: "#"
            }, {
                icon: "❤️",
                title: "믿는 사람에게 톡",
                content: "“요즘 좀 힘들어” 한 문장으로 시작해요."
            }, {
                icon: "🌁",
                title: "밤의 부담 덜기",
                content: "오늘 밤만큼은 나를 지치게 하는 앱 1개를 잠시 쉬어볼까요? 잠들기 전 마음을 보호해요."
            }]
        }
    };

    function updateUIState(score) {
        let startColor, endColor, riskLevel, guideKey, riskColor, riskIconPath;
        if (score <= 9) {
            riskLevel = '안정';
            riskColor = 'text-green-600';
            riskIconPath = 'M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z';
            startColor = '#D8E2C5';
            endColor = '#C8D7D8';
            guideKey = 'low';
        } else if (score <= 14) {
            riskLevel = '조절';
            riskColor = 'text-yellow-600';
            riskIconPath = 'M4 12h16';
            startColor = '#FFD580';
            endColor = '#F0E68C';
            guideKey = 'medium';
        } else {
            riskLevel = '연결';
            riskColor = 'text-red-600';
            riskIconPath = 'M12 20l1.41-1.41L7.83 13H20v-2H7.83l5.58-5.59L12 4l-8 8z';
            startColor = '#F97316';
            endColor = '#FFD580';
            guideKey = 'high';
        }

        document.documentElement.style.setProperty('--orb-color-start', startColor);
        document.documentElement.style.setProperty('--orb-color-end', endColor);
        phqScoreEl.textContent = score;
        phqRiskLevelEl.textContent = riskLevel;
        phqRiskContainer.className = `flex items-center justify-center gap-1 ${riskColor}`;
        phqRiskContainer.querySelector('path').setAttribute('d', riskIconPath);
        todayStatusMicrocopy.textContent = guideData[guideKey].microcopy;

        const guideCardsContainer = document.getElementById('guideCards');
        if (guideCardsContainer) {
            document.getElementById('guideSubtitle').textContent = guideData[guideKey].subtitle;
            guideCardsContainer.innerHTML = guideData[guideKey].cards.map(card => `
            <div class="guide-card text-left flex items-start gap-4">
              <div class="text-4xl mt-1">${card.icon}</div>
              <div>
                <h3 class="font-bold text-xl mb-1 text-gray-800">${card.title}</h3>
                <p class="text-gray-600">${card.content}</p>
                ${card.link ? `<a href="${card.link}" class="inline-block mt-4 px-4 py-2 text-sm font-semibold text-white rounded-full" style="background-color: var(--color-accent);">자세히 보기</a>` : ''}
              </div>
            </div>`).join('');
        }
    }

    function handleScroll() {
        requestAnimationFrame(() => {
            const scrollY = scrollContainer.scrollTop;
            const viewH = window.innerHeight;
            if (scrollY > 50) mainHeader.classList.add('bg-white/60', 'backdrop-blur-lg', 'shadow-sm');
            else mainHeader.classList.remove('bg-white/60', 'backdrop-blur-lg', 'shadow-sm');
            const progress = Math.min(1, scrollY / (viewH * (sections.length - 2)));
            orbStickyContainer.style.transform = `scale(${1 - progress})`;
            orbStickyContainer.style.opacity = 1 - progress;
        });
    }

    function openDetailView(topic) {
        const data = detailMockData[topic];
        if (!data) return;
        const originCard = document.querySelector(`.hub-bubble[data-topic="${topic}"]`);
        if (!originCard) return;
        originCardRect = originCard.getBoundingClientRect();

        detailTitleEl.textContent = data.title;
        detailInsightsEl.innerHTML = data.insights;
        const ctx = detailChartCanvas.getContext('2d');
        if (detailChart) detailChart.destroy();
        detailChart = new Chart(ctx, {
            type: data.chartData.type,
            data: {
                labels: data.chartData.labels,
                datasets: [{
                    label: data.title,
                    data: data.chartData.values,
                    backgroundColor: 'rgba(59,130,246,.2)',
                    borderColor: 'rgba(59,130,246,1)',
                    borderWidth: 2,
                    tension: .4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });

        detailContent.style.opacity = ''; // reset
        detailView.classList.add('active');
        detailCard.style.top = `${originCardRect.top}px`;
        detailCard.style.left = `${originCardRect.left}px`;
        detailCard.style.width = `${originCardRect.width}px`;
        detailCard.style.height = `${originCardRect.height}px`;
        requestAnimationFrame(() => {
            detailCard.style.top = '5vh';
            detailCard.style.left = '5vw';
            detailCard.style.width = '90vw';
            detailCard.style.height = '90vh';
        });
    }

    function closeDetailView() {
        if (!originCardRect) return;
        detailContent.style.opacity = '0';
        detailCard.style.top = `${originCardRect.top}px`;
        detailCard.style.left = `${originCardRect.left}px`;
        detailCard.style.width = `${originCardRect.width}px`;
        detailCard.style.height = `${originCardRect.height}px`;
        setTimeout(() => {
            detailView.classList.remove('active');
            detailContent.style.opacity = '';
        }, 600);
    }

    document.querySelectorAll('.hub-bubble').forEach(card => card.addEventListener('click', () => openDetailView(card.dataset.topic)));
    closeDetailBtn.addEventListener('click', closeDetailView);

    // 내부 앵커 스무스 스크롤
    document.querySelectorAll('a[href^="#"]').forEach(a => {
        a.addEventListener('click', (e) => {
            const id = a.getAttribute('href');
            const el = document.querySelector(id);
            if (el) {
                e.preventDefault();
                el.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });

    // 섹션 페이드인 + 네비 활성화
    const sectionObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            const sc = entry.target.querySelector('.section-content');
            if (sc) sc.classList.toggle('is-visible', entry.isIntersecting);
            if (entry.isIntersecting) {
                const id = entry.target.id;
                navLinks.forEach(link => link.classList.toggle('active', link.getAttribute('data-section') === id));
            }
        });
    }, {
        root: scrollContainer,
        threshold: .5
    });
    sections.forEach(section => sectionObserver.observe(section));

    // 초기
    document.querySelector('#heroPanel .section-content')?.classList.add('is-visible');
    scrollContainer.addEventListener('scroll', handleScroll, {
        passive: true
    });
    updateUIState(predictedScore);
    handleScroll();
    setInterval(() => {
        predictedScore = Math.floor(Math.random() * 28);
        updateUIState(predictedScore);
    }, 5000);

    // 스모크 테스트
    try {
        console.table([{
            name: '섹션 수',
            pass: document.querySelectorAll('.snap-section').length > 0
        }, {
            name: '히어로 표시',
            pass: document.querySelector('#heroPanel .section-content')?.classList.contains('is-visible') === true
        }]);
    } catch (e) {}
});