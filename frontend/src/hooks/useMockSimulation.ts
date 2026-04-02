import { useEffect, useState } from 'react'
import type { SimState } from './useSimulation'
import type { Platform, SocialPost } from '../types'

export const MOCK_SOURCES = [
  { source: 'github', title: 'vercel/next.js — The React Framework', snippet: 'Next.js gives you the best developer experience with all the features you need for production.' },
  { source: 'arxiv', title: 'Attention Is All You Need', snippet: 'We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.' },
  { source: 'hackernews', title: 'Show HN: I built a tool to simulate social media reactions to your product', snippet: '600 points · 142 comments · submitted 3 hours ago by tkpark' },
  { source: 'semantic_scholar', title: 'BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding', snippet: 'We introduce a new language representation model called BERT, which stands for Bidirectional Encoder Representations from Transformers.' },
  { source: 'reddit', title: 'Launched my SaaS last week – here\'s what I learned about positioning', snippet: 'After 6 months of building, I finally shipped. The response was... mixed. Here\'s what I wish I knew about messaging.' },
  { source: 'github', title: 'langchain-ai/langchain — Build context-aware reasoning applications', snippet: 'LangChain is a framework for developing applications powered by large language models.' },
  { source: 'product_hunt', title: 'Noosphere – Simulate real-world market reactions to your product', snippet: '🚀 Featured on Product Hunt · 342 upvotes · AI-powered social simulation' },
  { source: 'arxiv', title: 'Scaling Laws for Neural Language Models', snippet: 'We study empirical scaling laws for language model performance on the cross-entropy loss. The loss scales as a power-law with model size, dataset size, and the amount of compute used for training.' },
  { source: 'hackernews', title: 'Why most "AI wrappers" fail within 6 months', snippet: '891 points · 304 comments · A honest post-mortem from a YC founder.' },
  { source: 'reddit', title: 'What\'s your stack for validating startup ideas before building?', snippet: 'r/startups · 1.2k upvotes · I\'ve been using a mix of fake door tests and landing pages, but curious what others do.' },
  { source: 'serper', title: 'Market Simulation Tools — 2024 Roundup', snippet: 'Top AI-powered tools for simulating market reactions, user feedback, and community discussions before launch.' },
  { source: 'google_play', title: 'AI Chat Assistant — 4.2★ · 10M+ downloads', snippet: 'Smart AI assistant powered by the latest language models. Instant answers, creative writing, code help.' },
]

export const MOCK_PERSONAS = [
  { name: 'Marcus Chen', role: 'Senior Software Engineer', platform: 'hackernews' as Platform },
  { name: 'Sarah K.', role: 'Product Manager', platform: 'linkedin' as Platform },
  { name: 'devdave42', role: 'Indie Hacker', platform: 'indiehackers' as Platform },
  { name: 'VentureVC_Alex', role: 'VC Analyst', platform: 'reddit_startups' as Platform },
  { name: 'TechSkeptic99', role: 'Staff Engineer', platform: 'hackernews' as Platform },
  { name: 'priya_builds', role: 'Founder', platform: 'producthunt' as Platform },
  { name: 'james_pm', role: 'Head of Product', platform: 'linkedin' as Platform },
  { name: 'nocodeNate', role: 'No-code builder', platform: 'indiehackers' as Platform },
  { name: 'rachel_cto', role: 'CTO', platform: 'hackernews' as Platform },
  { name: 'bootstrapped_bo', role: 'Bootstrapped founder', platform: 'reddit_startups' as Platform },
]

export const MOCK_POSTS: Array<{ author_name: string; platform: Platform; action_type: string; content: string }> = [
  { author_name: 'Marcus Chen', platform: 'hackernews', action_type: 'comment', content: 'Interesting concept. The biggest risk I see is that simulated reactions might not capture the nuance of actual HN culture — we\'re famously unpredictable. That said, for early validation this could be genuinely useful.' },
  { author_name: 'priya_builds', platform: 'producthunt', action_type: 'review', content: '🚀 This is exactly what I needed before my last launch. Would have saved me weeks of misaligned positioning. Upvoted!' },
  { author_name: 'TechSkeptic99', platform: 'hackernews', action_type: 'comment', content: 'Another AI wrapper? The real question is how accurately it models different community subcultures. Reddit r/startups vs HN have very different signal-to-noise ratios. Show me the methodology.' },
  { author_name: 'devdave42', platform: 'indiehackers', action_type: 'post', content: 'Just tried this on my SaaS landing page. The Reddit simulation was surprisingly accurate — called out my vague value prop immediately. Highly recommend running this before you ship.' },
  { author_name: 'VentureVC_Alex', platform: 'reddit_startups', action_type: 'comment', content: 'From an investment standpoint, tools that reduce go-to-market uncertainty are always interesting. The question is repeatability. One good simulation doesn\'t make a moat.' },
  { author_name: 'sarah_k', platform: 'linkedin', action_type: 'post', content: 'Just discovered Noosphere and I\'m genuinely impressed. As a PM, the ability to stress-test messaging across different communities before launch is massive. The persona diversity feels real.' },
  { author_name: 'rachel_cto', platform: 'hackernews', action_type: 'comment', content: 'The technical implementation here is more interesting than the product surface suggests. LLM-based agent simulation with network effects modeled in? Someone did their homework on social dynamics research.' },
  { author_name: 'nocodeNate', platform: 'indiehackers', action_type: 'comment', content: 'Does this work for non-technical products? I build no-code tools and my users are not developers. Curious if the personas can capture that audience accurately.' },
  { author_name: 'bootstrapped_bo', platform: 'reddit_startups', action_type: 'post', content: 'Running this on my B2B SaaS tonight. Will report back. The free tier seems generous for what you get. Anyone else tried it on enterprise positioning?' },
  { author_name: 'james_pm', platform: 'linkedin', action_type: 'comment', content: 'Shared this with our GTM team. The LinkedIn simulation is uncannily accurate — right down to the corporate buzzword patterns. 😄 Solid product.' },
]

function makePost(idx: number, roundNum: number): SocialPost {
  const p = MOCK_POSTS[idx % MOCK_POSTS.length]
  return {
    id: `mock-${roundNum}-${idx}`,
    platform: p.platform,
    author_node_id: `node-${idx}`,
    author_name: p.author_name,
    content: p.content,
    action_type: p.action_type,
    round_num: roundNum,
    upvotes: Math.floor(Math.random() * 80),
    downvotes: Math.floor(Math.random() * 5),
    parent_id: null,
  }
}

export function useMockSimulation(): SimState {
  const [state, setState] = useState<SimState>({
    status: 'connecting',
    events: [],
    postsByPlatform: {},
    report: null,
    personas: null,
    analysisMd: '',
    errorMsg: '',
    roundNum: 0,
    agentCount: 0,
    personaCount: 0,
    sourceTimeline: [],
    graphData: null,
    isSourcing: false,
    streamingPersonas: {},
    roundStats: [],
    lastRound: 0,
    backendStatus: null,
    canResume: false,
    warnings: [],
    liveSentiment: { positive: 0, neutral: 0, negative: 0 },
    earlyStop: null,
    personaGenPhase: false,
  })

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = []
    let t = 0

    const at = (delay: number, fn: () => void) => {
      t += delay
      timers.push(setTimeout(fn, t))
    }

    // 소스 수집 단계
    at(400, () => setState(s => ({ ...s, status: 'running',
      events: [...s.events, { type: 'sim_progress', message: 'Searching external sources...' }]
    })))

    MOCK_SOURCES.forEach((src, i) => {
      at(i === 0 ? 600 : 320, () => {
        setState(s => ({
          ...s,
          sourceTimeline: [{ source: src.source, title: src.title, snippet: src.snippet }, ...s.sourceTimeline],
        }))
      })
    })

    // 분석 리포트
    at(500, () => setState(s => ({
      ...s,
      events: [...s.events, { type: 'sim_progress', message: 'Domain: AI/Developer Tools. Generating analysis report...' }],
    })))

    at(800, () => setState(s => ({
      ...s,
      analysisMd: '## Analysis\n\nMarket context looks strong for this category.',
      sourceTimeline: [],
    })))

    // 시뮬레이션 시작
    at(600, () => setState(s => ({
      ...s,
      agentCount: 10,
      events: [...s.events, { type: 'sim_progress', message: 'Starting simulation with 12 context nodes...' }],
    })))

    // 페르소나 생성
    MOCK_PERSONAS.forEach((p, i) => {
      at(i === 0 ? 400 : 260, () => {
        setState(s => ({
          ...s,
          personaCount: s.personaCount + 1,
          events: [...s.events, { type: 'sim_persona', name: p.name, role: p.role, platform: p.platform }],
        }))
      })
    })

    // 라운드 1 포스트
    at(700, () => setState(s => ({
      ...s,
      events: [...s.events, { type: 'sim_round_summary', round_num: 1 }],
      roundNum: 1,
    })))

    for (let i = 0; i < 6; i++) {
      at(i === 0 ? 300 : 400, () => {
        const post = makePost(i, 1)
        setState(s => {
          const posts = { ...s.postsByPlatform }
          posts[post.platform] = [...(posts[post.platform] || []), post]
          return { ...s, postsByPlatform: posts }
        })
      })
    }

    // 라운드 2 포스트
    at(600, () => setState(s => ({
      ...s,
      events: [...s.events, { type: 'sim_round_summary', round_num: 2 }],
      roundNum: 2,
    })))

    for (let i = 6; i < 10; i++) {
      at(i === 6 ? 200 : 380, () => {
        const post = makePost(i, 2)
        setState(s => {
          const posts = { ...s.postsByPlatform }
          posts[post.platform] = [...(posts[post.platform] || []), post]
          return { ...s, postsByPlatform: posts }
        })
      })
    }

    // 시뮬레이션 완료
    at(1200, () => setState(s => ({ ...s, status: 'done' })))

    return () => timers.forEach(clearTimeout)
  }, [])

  return state
}
