import { useRef, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion, useInView } from 'framer-motion'
import { Button } from 'antd'
import { ArrowRightOutlined, CheckOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'

/* ---------- animation helpers ---------- */
function FadeInSection({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-60px' })
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 40 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, delay, ease: 'easeOut' }}
    >
      {children}
    </motion.div>
  )
}

/* ---------- data ---------- */

/* ---------- styles ---------- */
const sectionStyle: React.CSSProperties = {
  maxWidth: 1200,
  margin: '0 auto',
  padding: '100px 24px',
}

const sectionTitle: React.CSSProperties = {
  fontSize: 36,
  fontWeight: 800,
  color: '#f1f5f9',
  textAlign: 'center',
  marginBottom: 16,
}

const sectionSub: React.CSSProperties = {
  fontSize: 16,
  color: '#94a3b8',
  textAlign: 'center',
  marginBottom: 60,
  maxWidth: 600,
  marginLeft: 'auto',
  marginRight: 'auto',
}

/* ---------- component ---------- */
export default function LandingPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const FEATURES = [
    { icon: '\u{1F916}', title: t('landing.featureAgent'), desc: t('landing.featureAgentDesc') },
    { icon: '\u{1F517}', title: t('landing.featureMcp'), desc: t('landing.featureMcpDesc') },
    { icon: '\u{1F4DA}', title: t('landing.featureKnowledge'), desc: t('landing.featureKnowledgeDesc') },
    { icon: '\u{1F9E9}', title: t('landing.featurePlugin'), desc: t('landing.featurePluginDesc') },
  ]

  const STEPS = [
    { num: '01', title: t('landing.step1Title'), desc: t('landing.step1Desc') },
    { num: '02', title: t('landing.step2Title'), desc: t('landing.step2Desc') },
    { num: '03', title: t('landing.step3Title'), desc: t('landing.step3Desc') },
  ]

  const PLANS = [
    {
      name: t('landing.planFree'), price: '0', period: t('landing.perMonth'), badge: '',
      features: [t('landing.planFreeF1'), t('landing.planFreeF2'), t('landing.planFreeF3'), t('landing.planFreeF4')],
      cta: t('landing.planFreeCta'), highlight: false,
    },
    {
      name: t('landing.planPro'), price: '299', period: t('landing.perMonth'), badge: t('landing.planProBadge'),
      features: [t('landing.planProF1'), t('landing.planProF2'), t('landing.planProF3'), t('landing.planProF4'), t('landing.planProF5'), t('landing.planProF6')],
      cta: t('landing.planProCta'), highlight: true,
    },
    {
      name: t('landing.planEnterprise'), price: t('landing.contactUs'), period: '', badge: '',
      features: [t('landing.planEnterpriseF1'), t('landing.planEnterpriseF2'), t('landing.planEnterpriseF3'), t('landing.planEnterpriseF4'), t('landing.planEnterpriseF5'), t('landing.planEnterpriseF6')],
      cta: t('landing.planEnterpriseCta'), highlight: false,
    },
  ]

  // Landing page needs scrolling — override global overflow:hidden
  useEffect(() => {
    const root = document.getElementById('root')
    if (root) {
      root.style.overflow = 'auto'
    }
    return () => {
      if (root) {
        root.style.overflow = ''
      }
    }
  }, [])

  return (
    <div
      style={{
        background: '#0a0e1a',
        minHeight: '100vh',
        position: 'relative',
      }}
    >
      {/* Ambient glow */}
      <div
        style={{
          position: 'fixed',
          inset: 0,
          pointerEvents: 'none',
          zIndex: 0,
        }}
      >
        <div
          style={{
            position: 'absolute',
            width: '100%',
            maxWidth: 800,
            height: 800,
            borderRadius: '50%',
            background:
              'radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%)',
            top: -300,
            left: '50%',
            transform: 'translateX(-50%)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            width: 600,
            height: 600,
            borderRadius: '50%',
            background:
              'radial-gradient(circle, rgba(139,92,246,0.08) 0%, transparent 70%)',
            bottom: -200,
            right: -100,
          }}
        />
      </div>

      {/* Nav */}
      <nav
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 50,
          backdropFilter: 'blur(16px)',
          background: 'rgba(10,14,26,0.8)',
          borderBottom: '1px solid rgba(148,163,184,0.08)',
        }}
      >
        <div
          style={{
            maxWidth: 1200,
            margin: '0 auto',
            padding: '0 24px',
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 24 }}>{'\u26A1'}</span>
            <span
              style={{
                fontSize: 20,
                fontWeight: 800,
                background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              BridgeAI
            </span>
          </div>
          <div style={{ display: 'flex', gap: 32, alignItems: 'center' }}>
            <a href="#features" style={{ color: '#94a3b8', textDecoration: 'none', fontSize: 14 }}>
              {t('landing.features')}
            </a>
            <a href="#pricing" style={{ color: '#94a3b8', textDecoration: 'none', fontSize: 14 }}>
              {t('landing.pricing')}
            </a>
            <Link to="/docs" style={{ color: '#94a3b8', textDecoration: 'none', fontSize: 14 }}>
              {t('landing.docs')}
            </Link>
            <Button
              type="primary"
              size="small"
              onClick={() => navigate('/login')}
            >
              {t('login.login')}
            </Button>
          </div>
        </div>
      </nav>

      {/* ===== HERO ===== */}
      <section style={{ ...sectionStyle, paddingTop: 120, paddingBottom: 80, position: 'relative', zIndex: 1 }}>
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          style={{ textAlign: 'center' }}
        >
          <h1
            style={{
              fontSize: 'clamp(32px, 6vw, 72px)',
              fontWeight: 900,
              lineHeight: 1.1,
              marginBottom: 24,
              background: 'linear-gradient(135deg,#f1f5f9 30%,#6366f1 70%,#8b5cf6)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              letterSpacing: -2,
            }}
          >
            BridgeAI
          </h1>
          <p
            style={{
              fontSize: 24,
              color: '#cbd5e1',
              fontWeight: 400,
              marginBottom: 48,
              maxWidth: 520,
              marginLeft: 'auto',
              marginRight: 'auto',
              lineHeight: 1.5,
            }}
          >
            {t('landing.heroSubtitle')}
          </p>
          <motion.div
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.98 }}
            style={{ display: 'inline-block' }}
          >
            <button
              onClick={() => navigate('/login')}
              style={{
                padding: '16px 48px',
                fontSize: 18,
                fontWeight: 700,
                color: '#fff',
                border: 'none',
                borderRadius: 12,
                cursor: 'pointer',
                background: 'linear-gradient(135deg,#6366f1,#8b5cf6,#a855f7)',
                boxShadow:
                  '0 8px 32px rgba(99,102,241,0.4), inset 0 1px 0 rgba(255,255,255,0.1)',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
              }}
            >
              {t('landing.getStarted')} <ArrowRightOutlined />
            </button>
          </motion.div>
        </motion.div>
      </section>

      {/* ===== FEATURES ===== */}
      <section id="features" style={{ ...sectionStyle, position: 'relative', zIndex: 1 }}>
        <FadeInSection>
          <h2 style={sectionTitle}>{t('landing.featureTitle')}</h2>
          <p style={sectionSub}>{t('landing.featureSubtitle')}</p>
        </FadeInSection>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 24,
          }}
        >
          {FEATURES.map((f, i) => (
            <FadeInSection key={f.title} delay={i * 0.1}>
              <div
                style={{
                  padding: 32,
                  borderRadius: 16,
                  background: 'rgba(17,24,39,0.6)',
                  border: '1px solid rgba(148,163,184,0.1)',
                  backdropFilter: 'blur(12px)',
                  transition: 'all 0.3s',
                  height: '100%',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'rgba(99,102,241,0.4)'
                  e.currentTarget.style.boxShadow = '0 8px 40px rgba(99,102,241,0.12)'
                  e.currentTarget.style.transform = 'translateY(-4px)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'rgba(148,163,184,0.1)'
                  e.currentTarget.style.boxShadow = 'none'
                  e.currentTarget.style.transform = 'translateY(0)'
                }}
              >
                <div style={{ fontSize: 40, marginBottom: 16 }}>{f.icon}</div>
                <h3 style={{ fontSize: 20, fontWeight: 700, color: '#f1f5f9', marginBottom: 8 }}>
                  {f.title}
                </h3>
                <p style={{ fontSize: 14, color: '#94a3b8', lineHeight: 1.7 }}>{f.desc}</p>
              </div>
            </FadeInSection>
          ))}
        </div>
      </section>

      {/* ===== HOW IT WORKS ===== */}
      <section style={{ ...sectionStyle, position: 'relative', zIndex: 1 }}>
        <FadeInSection>
          <h2 style={sectionTitle}>{t('landing.stepsTitle')}</h2>
          <p style={sectionSub}>{t('landing.stepsSubtitle')}</p>
        </FadeInSection>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: 32,
          }}
        >
          {STEPS.map((s, i) => (
            <FadeInSection key={s.num} delay={i * 0.15}>
              <div style={{ textAlign: 'center' }}>
                <div
                  style={{
                    width: 72,
                    height: 72,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg,rgba(99,102,241,0.15),rgba(139,92,246,0.15))',
                    border: '2px solid rgba(99,102,241,0.3)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    margin: '0 auto 20px',
                    fontSize: 24,
                    fontWeight: 800,
                    color: '#818cf8',
                  }}
                >
                  {s.num}
                </div>
                <h3 style={{ fontSize: 20, fontWeight: 700, color: '#f1f5f9', marginBottom: 8 }}>
                  {s.title}
                </h3>
                <p style={{ fontSize: 14, color: '#94a3b8', lineHeight: 1.6 }}>{s.desc}</p>
              </div>
            </FadeInSection>
          ))}
        </div>
      </section>

      {/* ===== PRICING ===== */}
      <section id="pricing" style={{ ...sectionStyle, position: 'relative', zIndex: 1 }}>
        <FadeInSection>
          <h2 style={sectionTitle}>{t('landing.pricingTitle')}</h2>
          <p style={sectionSub}>{t('landing.pricingSubtitle')}</p>
        </FadeInSection>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
            gap: 24,
            alignItems: 'stretch',
          }}
        >
          {PLANS.map((plan, i) => (
            <FadeInSection key={plan.name} delay={i * 0.1}>
              <div
                style={{
                  padding: 36,
                  borderRadius: 16,
                  background: plan.highlight
                    ? 'linear-gradient(180deg,rgba(99,102,241,0.12) 0%,rgba(17,24,39,0.8) 100%)'
                    : 'rgba(17,24,39,0.6)',
                  border: plan.highlight
                    ? '2px solid rgba(99,102,241,0.5)'
                    : '1px solid rgba(148,163,184,0.1)',
                  backdropFilter: 'blur(12px)',
                  position: 'relative',
                  display: 'flex',
                  flexDirection: 'column',
                  height: '100%',
                }}
              >
                {plan.badge && (
                  <div
                    style={{
                      position: 'absolute',
                      top: -14,
                      left: '50%',
                      transform: 'translateX(-50%)',
                      padding: '4px 20px',
                      borderRadius: 20,
                      background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
                      fontSize: 13,
                      fontWeight: 600,
                      color: '#fff',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {plan.badge}
                  </div>
                )}

                <h3
                  style={{
                    fontSize: 22,
                    fontWeight: 700,
                    color: '#f1f5f9',
                    marginBottom: 16,
                    textAlign: 'center',
                  }}
                >
                  {plan.name}
                </h3>
                <div style={{ textAlign: 'center', marginBottom: 28 }}>
                  <span
                    style={{
                      fontSize: plan.price === t('landing.contactUs') ? 28 : 48,
                      fontWeight: 900,
                      color: '#f1f5f9',
                    }}
                  >
                    {plan.price === t('landing.contactUs') ? '' : '\u00A5'}
                    {plan.price}
                  </span>
                  <span style={{ fontSize: 14, color: '#94a3b8' }}>{plan.period}</span>
                </div>

                <ul style={{ listStyle: 'none', padding: 0, flex: 1, marginBottom: 28 }}>
                  {plan.features.map((feat) => (
                    <li
                      key={feat}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        padding: '8px 0',
                        fontSize: 14,
                        color: '#cbd5e1',
                      }}
                    >
                      <CheckOutlined style={{ color: '#6366f1', fontSize: 14 }} />
                      {feat}
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => navigate('/login')}
                  style={{
                    width: '100%',
                    padding: '12px 0',
                    borderRadius: 10,
                    border: plan.highlight ? 'none' : '1px solid rgba(148,163,184,0.2)',
                    background: plan.highlight
                      ? 'linear-gradient(135deg,#6366f1,#8b5cf6)'
                      : 'transparent',
                    color: plan.highlight ? '#fff' : '#cbd5e1',
                    fontSize: 15,
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                >
                  {plan.cta}
                </button>
              </div>
            </FadeInSection>
          ))}
        </div>
      </section>

      {/* ===== FOOTER ===== */}
      <footer
        style={{
          borderTop: '1px solid rgba(148,163,184,0.08)',
          position: 'relative',
          zIndex: 1,
        }}
      >
        <div
          style={{
            maxWidth: 1200,
            margin: '0 auto',
            padding: '40px 24px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 16,
          }}
        >
          <span style={{ fontSize: 13, color: '#64748b' }}>
            &copy; {new Date().getFullYear()} BridgeAI. All rights reserved.
          </span>
          <div style={{ display: 'flex', gap: 24 }}>
            <Link to="/docs" style={{ fontSize: 13, color: '#64748b', textDecoration: 'none' }}>
              {t('landing.docs')}
            </Link>
            <a href="#pricing" style={{ fontSize: 13, color: '#64748b', textDecoration: 'none' }}>
              {t('landing.pricing')}
            </a>
            <a href="mailto:1178672658@qq.com" style={{ fontSize: 13, color: '#64748b', textDecoration: 'none' }}>
              {t('landing.footerContact')}
            </a>
          </div>
        </div>
      </footer>
    </div>
  )
}
