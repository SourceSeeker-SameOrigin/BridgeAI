import { useState, useRef, useCallback, useEffect } from 'react'
import { Input, Button, Tooltip, message, Tag, Spin } from 'antd'
import {
  SendOutlined,
  PaperClipOutlined,
  AudioOutlined,
  FileTextOutlined,
  CloseOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { uploadFileForChat } from '../../api/notifications'

const { TextArea } = Input

interface FileAttachment {
  filename: string
  content: string
  fileSize: number
  truncated: boolean
}

interface InputBarProps {
  onSend: (message: string) => void
  disabled?: boolean
}

const SpeechRecognitionCtor =
  typeof window !== 'undefined'
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null

export default function InputBar({ onSend, disabled }: InputBarProps) {
  const [value, setValue] = useState('')
  const [attachment, setAttachment] = useState<FileAttachment | null>(null)
  const [uploading, setUploading] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const textAreaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { t: _t } = useTranslation()
  void _t // keep import for future use

  // Clean up recognition on unmount
  useEffect(() => {
    return () => {
      recognitionRef.current?.abort()
    }
  }, [])

  // Track interim transcript for live display
  const [interimText, setInterimText] = useState('')

  const startListening = useCallback(() => {
    if (!SpeechRecognitionCtor) {
      message.warning('您的浏览器不支持语音输入，请使用 Chrome 浏览器')
      return
    }
    try {
      const recognition = new SpeechRecognitionCtor()
      recognition.lang = 'zh-CN'
      recognition.continuous = true
      recognition.interimResults = true
      recognition.maxAlternatives = 1

      recognition.onstart = () => {
        setIsListening(true)
        setInterimText('')
        message.info('正在录音，请说话...')
      }

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        let finalTranscript = ''
        let interim = ''
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i]
          if (result.isFinal) {
            finalTranscript += result[0].transcript
          } else {
            interim += result[0].transcript
          }
        }
        if (finalTranscript) {
          setValue((prev) => prev + finalTranscript)
          setInterimText('')
        } else {
          setInterimText(interim)
        }
      }

      recognition.onend = () => {
        setIsListening(false)
        setInterimText('')
      }

      recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
        setIsListening(false)
        setInterimText('')
        const errorMap: Record<string, string> = {
          'not-allowed': '麦克风权限被拒绝，请在浏览器设置中允许使用麦克风',
          'no-speech': '未检测到语音，请重试',
          'audio-capture': '未找到麦克风设备',
          'network': '网络错误，语音识别需要网络连接',
          'aborted': '语音识别已取消',
        }
        const msg = errorMap[event.error] || `语音识别失败: ${event.error}`
        message.error(msg)
      }

      recognitionRef.current = recognition
      recognition.start()
    } catch (err) {
      message.error('启动语音识别失败，请检查浏览器是否支持')
      setIsListening(false)
    }
  }, [])

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
    }
    setIsListening(false)
    setInterimText('')
  }, [])

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if ((!trimmed && !attachment) || disabled) return

    let finalMessage = trimmed
    if (attachment) {
      // Prepend file content as context
      const fileContext = `[附件: ${attachment.filename}]\n\n${attachment.content}\n\n---\n\n`
      finalMessage = fileContext + (trimmed || `请分析上传的文件 "${attachment.filename}"`)
    }

    onSend(finalMessage)
    setValue('')
    setAttachment(null)
  }, [value, attachment, disabled, onSend])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend],
  )

  const handleFileClick = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (!file) return

      // Reset file input so the same file can be re-selected
      e.target.value = ''

      // Check file size client-side (10MB)
      if (file.size > 10 * 1024 * 1024) {
        message.error('文件大小不能超过 10MB')
        return
      }

      setUploading(true)
      try {
        const result = await uploadFileForChat(file)
        setAttachment({
          filename: result.filename,
          content: result.content,
          fileSize: result.fileSize,
          truncated: result.truncated,
        })
        if (result.truncated) {
          message.warning('文件内容过长，已截取前部分内容')
        }
      } catch (err: unknown) {
        const errorMsg = err instanceof Error ? err.message : '上传失败'
        message.error(`文件上传失败: ${errorMsg}`)
      } finally {
        setUploading(false)
      }
    },
    [],
  )

  const handleRemoveAttachment = useCallback(() => {
    setAttachment(null)
  }, [])

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div
      style={{
        padding: '16px 20px',
        borderTop: '1px solid rgba(148,163,184,0.1)',
        background: 'rgba(17,24,39,0.5)',
        backdropFilter: 'blur(12px)',
      }}
    >
      {/* Attachment Preview */}
      {attachment && (
        <div
          style={{
            maxWidth: 900,
            margin: '0 auto 8px',
            padding: '8px 12px',
            background: 'rgba(99,102,241,0.1)',
            border: '1px solid rgba(99,102,241,0.2)',
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <FileTextOutlined style={{ color: '#818cf8', fontSize: 16 }} />
          <span style={{ color: '#c7d2fe', fontSize: 13, flex: 1 }}>
            {attachment.filename}
          </span>
          <Tag
            style={{
              background: 'rgba(99,102,241,0.15)',
              borderColor: 'transparent',
              color: '#a5b4fc',
              fontSize: 11,
            }}
          >
            {formatFileSize(attachment.fileSize)}
          </Tag>
          {attachment.truncated && (
            <Tag
              color="warning"
              style={{ fontSize: 11 }}
            >
              已截取
            </Tag>
          )}
          <CloseOutlined
            onClick={handleRemoveAttachment}
            style={{ color: '#94a3b8', cursor: 'pointer', fontSize: 12 }}
          />
        </div>
      )}

      <div
        style={{
          display: 'flex',
          gap: 12,
          alignItems: 'flex-end',
          maxWidth: 900,
          margin: '0 auto',
        }}
      >
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          style={{ display: 'none' }}
          accept=".txt,.pdf,.docx,.xlsx,.md,.csv,.json,.xml,.yaml,.yml,.log,.text"
          onChange={handleFileChange}
        />

        {/* Attachment Button */}
        <Tooltip title="上传文件">
          <Button
            type="text"
            icon={
              uploading ? (
                <Spin indicator={<LoadingOutlined style={{ fontSize: 16 }} />} />
              ) : (
                <PaperClipOutlined />
              )
            }
            onClick={handleFileClick}
            disabled={uploading || disabled}
            style={{ color: attachment ? '#818cf8' : '#64748b', height: 40, width: 40 }}
          />
        </Tooltip>

        {/* Text Input */}
        <div style={{ flex: 1, position: 'relative' }}>
          {isListening && (
            <div style={{
              position: 'absolute',
              top: -28,
              left: 0,
              fontSize: 12,
              color: '#ef4444',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              zIndex: 1,
            }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%',
                background: '#ef4444',
                animation: 'pulse 1s ease-in-out infinite',
                display: 'inline-block',
              }} />
              正在录音...
              {interimText && <span style={{ color: '#94a3b8', marginLeft: 4 }}>「{interimText}」</span>}
            </div>
          )}
          <TextArea
            ref={textAreaRef as never}
            value={isListening && interimText ? value + interimText : value}
            onChange={(e) => { if (!isListening) setValue(e.target.value) }}
            onKeyDown={handleKeyDown}
            placeholder={
              isListening
                ? '正在识别语音...'
                : attachment
                  ? `基于 ${attachment.filename} 提问...`
                  : '输入消息...'
            }
            autoSize={{ minRows: 1, maxRows: 5 }}
            disabled={disabled}
            style={{
              background: 'rgba(26,35,50,0.8)',
              border: '1px solid rgba(148,163,184,0.15)',
              borderRadius: 12,
              padding: '10px 14px',
              fontSize: 14,
              color: '#f1f5f9',
              resize: 'none',
            }}
          />
        </div>

        {/* Voice Button */}
        <Tooltip title={isListening ? '点击停止录音' : '语音输入'}>
          <div
            onClick={isListening ? stopListening : startListening}
            className={isListening ? 'voice-btn-recording' : ''}
            style={{
              width: 40,
              height: 40,
              borderRadius: 10,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: disabled ? 'not-allowed' : 'pointer',
              color: isListening ? '#fff' : '#64748b',
              background: isListening ? '#ef4444' : 'transparent',
              boxShadow: isListening ? '0 0 0 4px rgba(239,68,68,0.3)' : 'none',
              transition: 'all 0.2s ease',
              fontSize: 16,
              opacity: disabled ? 0.4 : 1,
            }}
          >
            <AudioOutlined />
          </div>
        </Tooltip>

        {/* Send Button */}
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          disabled={disabled || (!value.trim() && !attachment)}
          style={{
            height: 40,
            width: 40,
            borderRadius: 10,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        />
      </div>
    </div>
  )
}
