import { useEffect, useState } from 'react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export default function AboutPage() {
  const [readme, setReadme] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadAbout = async () => {
      try {
        const response = await fetch('/ABOUT.md')
        const text = await response.text()
        setReadme(text)
      } catch {
        setReadme('加载 ABOUT 失败')
      } finally {
        setLoading(false)
      }
    }
    loadAbout()
  }, [])

  const formatMarkdown = (text) => {
    if (!text) return ''

    return text
      .replace(/^# (.*$)/gim, '<h1 class="text-3xl font-bold mb-4">$1</h1>')
      .replace(/^## (.*$)/gim, '<h2 class="text-2xl font-bold mb-3 mt-6">$1</h2>')
      .replace(/^### (.*$)/gim, '<h3 class="text-xl font-bold mb-2 mt-4">$1</h3>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.*?)`/g, '<code class="bg-gray-100 px-1 py-0.5 rounded text-sm">$1</code>')
      .replace(/```(\w*)([\s\S]*?)```/g, '<pre class="bg-gray-900 text-gray-100 p-4 rounded-lg my-4 overflow-x-auto"><code>$2</code></pre>')
      .replace(/```/g, '</pre>')
      .replace(/\n/g, '<br/>')
  }

  if (loading) {
    return (
      <div className='mx-auto max-w-7xl p-4 pb-8 md:p-8'>
        <Card>
          <CardContent className='p-8 text-center'>
            <p className='text-muted-foreground'>加载中...</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className='mx-auto max-w-7xl p-4 pb-8 md:p-8'>
      <Card>
        <CardHeader>
          <CardTitle>关于 EmbyQ</CardTitle>
        </CardHeader>
        <CardContent className='prose max-w-none'>
          <div className='markdown-content' dangerouslySetInnerHTML={{ __html: formatMarkdown(readme) }} />
        </CardContent>
      </Card>
    </div>
  )
}
