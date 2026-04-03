import { useEffect, useMemo, useRef, useState } from 'react'
import { Angry, CircleCheckBig, Film, Heart, Loader, LoaderCircle, Play, Search, Tv, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import UserIdentity from '@/components/UserIdentity'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogClose, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { apiRequest } from '@/types/api'

const REQUEST_STATUS_LABELS = {
  pending: '待处理',
  approved: '已采纳',
  rejected: '已拒绝',
}

function normalizeWishItem(item) {
  return {
    ...item,
    requested: true,
    request_status: item.request_status || item.status || 'pending',
  }
}

function SeasonDetailModal({ open, onClose, item, loading, seasons, librarySeasonCount, onSubmitSeason }) {
  const [submittingSeason, setSubmittingSeason] = useState(null)
  const [wishListSeasons, setWishListSeasons] = useState(new Set())

  const handleSubmitSeason = async (season) => {
    setSubmittingSeason(season.season_number)
    try {
      await onSubmitSeason(season, item)
      setWishListSeasons((prev) => new Set([...prev, season.season_number]))
    } finally {
      setSubmittingSeason(null)
    }
  }

  if (!open) return null

  return (
    <div className='fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4' onClick={onClose}>
      <Card className='flex max-h-[85vh] w-full max-w-4xl flex-col overflow-hidden' onClick={(e) => e.stopPropagation()}>
        <CardHeader className='shrink-0 border-b pb-4'>
          <div className='flex items-start justify-between gap-4'>
            <div>
              <CardTitle>{item?.title || item?.name || '剧集详情'}</CardTitle>
              <p className='mt-1 text-sm text-muted-foreground'>
                共 {seasons?.length || 0} 季，Emby库中已有 {librarySeasonCount || 0} 季
              </p>
            </div>
            <Button size='icon' variant='ghost' onClick={onClose} title='关闭'>
              <X className='h-4 w-4' />
            </Button>
          </div>
        </CardHeader>
        <CardContent className='min-h-0 flex-1 overflow-y-auto p-6'>
          {loading ? (
            <div className='flex items-center justify-center py-8'>
              <LoaderCircle className='h-6 w-6 animate-spin text-muted-foreground' />
            </div>
          ) : (
            <div className='space-y-2'>
              {seasons?.map((season) => {
                const inWishList = wishListSeasons.has(season.season_number)
                return (
                <div
                  key={season.season_number}
                  className={`flex items-center justify-between rounded-lg border p-3 ${
                    season.in_library
                      ? 'border-green-500/30 bg-green-500/5'
                      : inWishList
                        ? 'border-yellow-500/30 bg-yellow-500/5'
                        : 'border-blue-500/30 bg-blue-500/5'
                  }`}
                >
                  <div className='flex items-center gap-3'>
                    {season.poster_url ? (
                      <img src={season.poster_url} alt={season.name} className='h-12 w-8 rounded object-cover' />
                    ) : (
                      <div className='flex h-12 w-8 items-center justify-center rounded bg-muted text-xs text-muted-foreground'>
                        无图
                      </div>
                    )}
                    <div>
                      <div className='font-medium'>{season.name}</div>
                      <div className='text-xs text-muted-foreground'>
                        {season.air_date ? season.air_date.slice(0, 4) : '未知年份'}
                      </div>
                    </div>
                  </div>
                  <div className='flex items-center gap-2'>
                    {season.in_library ? (
                      <Badge className='bg-green-500 text-white'>已入库</Badge>
                    ) : inWishList ? (
                      <Badge className='bg-yellow-500 text-black'>已在清单中</Badge>
                    ) : (
                      <Button
                        size='sm'
                        className='border-2 border-blue-500 bg-blue-500 text-white hover:bg-blue-600'
                        onClick={() => handleSubmitSeason(season)}
                        disabled={submittingSeason === season.season_number}
                      >
                        {submittingSeason === season.season_number ? (
                          <LoaderCircle className='mr-1 h-4 w-4 animate-spin' />
                        ) : (
                          <Heart className='mr-1 h-4 w-4' />
                        )}
                        加入想看
                      </Button>
                    )}
                  </div>
                </div>
              )
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function WishPosterCard({ item, submittingId, onSubmit, onShowSeasonDetail }) {
  const key = `${item.media_type}-${item.tmdb_id}`
  const isSubmitting = submittingId === key
  const titleText = item.title || item.original_title || '未命名内容'
  const itemStatus = item.request_status || item.status
  const isRequested = Boolean(item.requested || item.request_id || item.id)
  const isApproved = itemStatus === 'approved'

  const isInLibrary = item.in_library
  const isPartiallyAvailable = item.media_type === 'tv' && isInLibrary && item.library_season_count > 0 && item.library_season_count < (item.tmdb_season_count || 0)

  const handleSubmit = () => {
    if (isSubmitting) return
    if (isPartiallyAvailable) {
      if (onShowSeasonDetail) onShowSeasonDetail(item)
      return
    }
    if (isRequested || isApproved) return
    onSubmit(item)
  }

  const handleCardClick = () => {
    if (isPartiallyAvailable) {
      if (onShowSeasonDetail) onShowSeasonDetail(item)
    }
  }

  return (
    <div
      role='button'
      tabIndex={isPartiallyAvailable ? 0 : isRequested || isApproved ? -1 : 0}
      className='flex h-full flex-col overflow-hidden rounded-lg border bg-card text-left transition-transform hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md'
      onClick={handleCardClick}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          handleSubmit()
        }
      }}
    >
      <div className='relative aspect-[3/4] w-full shrink-0 overflow-hidden bg-muted'>
        {item.poster_url ? (
          <img src={item.poster_url} alt={titleText} className='absolute inset-0 h-full w-full object-cover' />
        ) : (
          <div className='flex h-full items-center justify-center px-3 text-center text-xs text-muted-foreground'>暂无海报</div>
        )}
        {isPartiallyAvailable ? (
          <div className='absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/45 text-white'>
            <div className='flex h-10 w-10 items-center justify-center rounded-full bg-red-500/90 shadow-lg'>
              <Angry className='h-5 w-5' />
            </div>
            <span className='rounded-full bg-black/40 px-2.5 py-1 text-xs font-medium'>部分缺失</span>
          </div>
        ) : isApproved ? (
          <div className='absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/45 text-white'>
            <div className='flex h-10 w-10 items-center justify-center rounded-full bg-teal-500/90 shadow-lg'>
              <CircleCheckBig className='h-5 w-5' />
            </div>
            <span className='rounded-full bg-black/40 px-2.5 py-1 text-xs font-medium'>已采纳</span>
          </div>
        ) : isRequested && !isInLibrary ? (
          <div className='absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/45 text-white'>
            <div className='flex h-10 w-10 items-center justify-center rounded-full bg-yellow-500/90 shadow-lg'>
              <Loader className='h-5 w-5 animate-spin' />
            </div>
            <span className='rounded-full bg-black/40 px-2.5 py-1 text-xs font-medium'>已在清单中</span>
          </div>
        ) : isInLibrary ? (
          <div className='absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/45 text-white'>
            <div className='flex h-10 w-10 items-center justify-center rounded-full bg-green-500/90 shadow-lg'>
              <CircleCheckBig className='h-5 w-5' />
            </div>
            <span className='rounded-full bg-black/40 px-2.5 py-1 text-xs font-medium'>已入库</span>
          </div>
        ) : null}
      </div>
      <div className='flex h-[184px] flex-col gap-3 p-3'>
        <div className='flex flex-1 flex-col gap-2'>
          <div className='group relative h-5 w-full overflow-hidden'>
            <div className='truncate text-sm font-medium leading-5' title={titleText}>
              {titleText}
            </div>
            <div className='absolute left-0 top-0 h-5 w-full translate-x-[-100%] overflow-hidden whitespace-nowrap transition-transform duration-300 ease-in-out group-hover:translate-x-0 group-hover:bg-card'>
              <div className='text-sm font-medium leading-5' title={titleText}>
                {titleText}
              </div>
            </div>
          </div>
          <div className='flex items-center justify-between gap-1 text-[11px] text-muted-foreground'>
            <span className='truncate'>{item.year || item.release_date || '未知年份'}</span>
            <Badge variant='outline' className='h-5 shrink-0 px-1.5 text-[10px]'>
              {item.media_type === 'movie' ? (
                <span className='inline-flex items-center gap-1'>
                  <Film className='h-3 w-3' /> 电影
                </span>
              ) : (
                <span className='inline-flex items-center gap-1'>
                  <Tv className='h-3 w-3' /> 剧集
                </span>
              )}
            </Badge>
          </div>
          <p className='line-clamp-3 flex-1 text-xs leading-4 text-muted-foreground'>{item.overview || '暂无简介'}</p>
        </div>
        <Button
          type='button'
          size='sm'
          variant={isPartiallyAvailable ? 'default' : isInLibrary ? 'default' : 'default'}
          className={`h-10 w-full shrink-0 rounded-lg px-3 text-sm font-medium shadow-sm ${
            isPartiallyAvailable
              ? 'border-2 border-red-500 bg-red-500 text-white hover:bg-red-600'
              : isApproved
                ? 'border-2 border-teal-500 bg-teal-500 text-white hover:bg-teal-600'
                : isRequested && !isInLibrary
                  ? 'border-2 border-yellow-500 bg-yellow-500 text-black hover:bg-yellow-600'
                  : isInLibrary
                    ? 'border-2 border-green-500 bg-green-500 text-white hover:bg-green-600'
                    : 'border-2 border-blue-500 bg-blue-500 text-white hover:bg-blue-600'
          }`}
          disabled={isSubmitting}
          onClick={(event) => {
            event.stopPropagation()
            handleSubmit()
          }}
        >
          {isSubmitting ? (
            <LoaderCircle className='mr-2 h-4 w-4 animate-spin' />
          ) : isPartiallyAvailable ? (
            <Angry className='mr-2 h-4 w-4' />
          ) : isApproved ? (
            <CircleCheckBig className='mr-2 h-4 w-4' />
          ) : isRequested && !isInLibrary ? (
            <Loader className='mr-2 h-4 w-4 animate-spin' />
          ) : isInLibrary ? (
            <CircleCheckBig className='mr-2 h-4 w-4' />
          ) : (
            <Heart className='mr-2 h-4 w-4' />
          )}
          {isSubmitting
            ? '提交中...'
            : isPartiallyAvailable
              ? '部分缺失'
              : isApproved
                ? '已采纳'
                : isRequested && !isInLibrary
                  ? '已在清单中'
                  : isInLibrary
                    ? '已入库'
                    : '加入想看'}
        </Button>
      </div>
    </div>
  )
}

function WishListModal({
  open,
  onClose,
  items,
  loading,
  loadingMore,
  error,
  totalResults,
  page,
  totalPages,
  submittingId,
  onSubmit,
  onLoadMore,
  onShowSeasonDetail,
}) {
  if (!open) return null

  return (
    <div className='fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4' onClick={onClose}>
      <Card className='flex max-h-[88vh] w-full max-w-6xl flex-col overflow-hidden' onClick={(e) => e.stopPropagation()}>
        <CardHeader className='shrink-0 border-b pb-4'>
          <div className='flex items-start justify-between gap-4'>
            <div>
              <CardTitle>已求列表</CardTitle>
              <p className='mt-1 text-sm text-muted-foreground'>这里展示当前已经加入求片清单的影视内容。</p>
              {totalResults ? <p className='mt-1 text-xs text-muted-foreground'>共 {totalResults} 条</p> : null}
            </div>
            <Button size='icon' variant='ghost' onClick={onClose} title='关闭'>
              <X className='h-4 w-4' />
            </Button>
          </div>
        </CardHeader>
        <CardContent className='flex min-h-0 flex-1 flex-col gap-4 p-6'>
          {error ? <div className='shrink-0 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive'>{error}</div> : null}
          {loading ? <p className='shrink-0 text-sm text-muted-foreground'>正在加载已求列表...</p> : null}

          <div className='min-h-0 flex-1 overflow-y-auto pr-1'>
            <div className='grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5'>
              {items.map((item) => (
                <WishPosterCard key={`${item.media_type}-${item.tmdb_id}-${item.id || 'wish'}`} item={item} submittingId={submittingId} onSubmit={onSubmit} onShowSeasonDetail={onShowSeasonDetail} />
              ))}
            </div>

            {!loading && !items.length ? <p className='py-8 text-center text-sm text-muted-foreground'>当前还没有任何求片内容</p> : null}
          </div>

          {!loading && items.length && page < totalPages ? (
            <div className='flex shrink-0 justify-center'>
              <Button type='button' variant='outline' onClick={onLoadMore} disabled={loadingMore}>
                {loadingMore ? <LoaderCircle className='mr-2 h-4 w-4 animate-spin' /> : <ChevronDown className='mr-2 h-4 w-4' />}
                {loadingMore ? '加载中...' : '加载更多'}
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}

function RequestModal({ open, onClose }) {
  const [keyword, setKeyword] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [submittingId, setSubmittingId] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalResults, setTotalResults] = useState(0)
  const [wishListOpen, setWishListOpen] = useState(false)
  const [wishList, setWishList] = useState([])
  const [loadingWishList, setLoadingWishList] = useState(false)
  const [loadingWishListMore, setLoadingWishListMore] = useState(false)
  const [wishListError, setWishListError] = useState('')
  const [wishPage, setWishPage] = useState(1)
  const [wishTotalPages, setWishTotalPages] = useState(1)
  const [wishTotalResults, setWishTotalResults] = useState(0)
  const [seasonDetailOpen, setSeasonDetailOpen] = useState(false)
  const [seasonDetailItem, setSeasonDetailItem] = useState(null)
  const [seasonDetailLoading, setSeasonDetailLoading] = useState(false)
  const [seasonDetailSeasons, setSeasonDetailSeasons] = useState([])

  useEffect(() => {
    if (!open) {
      setKeyword('')
      setResults([])
      setLoading(false)
      setLoadingMore(false)
      setSubmittingId('')
      setError('')
      setNotice('')
      setPage(1)
      setTotalPages(1)
      setTotalResults(0)
      setWishListOpen(false)
      setWishList([])
      setLoadingWishList(false)
      setLoadingWishListMore(false)
      setWishListError('')
      setWishPage(1)
      setWishTotalPages(1)
      setWishTotalResults(0)
      setSeasonDetailOpen(false)
      setSeasonDetailItem(null)
      setSeasonDetailLoading(false)
      setSeasonDetailSeasons([])
    }
  }, [open])

  useEffect(() => {
    if (!wishListOpen) {
      setWishList([])
      setLoadingWishList(false)
      setLoadingWishListMore(false)
      setWishListError('')
      setWishPage(1)
      setWishTotalPages(1)
      setWishTotalResults(0)
      return
    }

    let active = true

    const loadWishList = async () => {
      setLoadingWishList(true)
      setWishListError('')
      try {
        const data = await apiRequest('/public/wishes?page=1&page_size=20')
        if (!active) return
        setWishList((data.requests || []).map(normalizeWishItem))
        setWishPage(data.page || 1)
        setWishTotalPages(data.total_pages || 1)
        setWishTotalResults(data.total_results || (data.requests || []).length)
      } catch (err) {
        if (active) {
          setWishListError(err.message)
          setWishList([])
          setWishPage(1)
          setWishTotalPages(1)
          setWishTotalResults(0)
        }
      } finally {
        if (active) setLoadingWishList(false)
      }
    }

    loadWishList()

    return () => {
      active = false
    }
  }, [wishListOpen])

  const onSearch = async (event) => {
    event.preventDefault()
    if (!keyword.trim()) return

    setLoading(true)
    setError('')
    setNotice('')
    setResults([])
    setPage(1)
    setTotalPages(1)
    setTotalResults(0)
    try {
      const data = await apiRequest(`/public/tmdb/search?q=${encodeURIComponent(keyword.trim())}&page=1`)
      setResults(data.results || [])
      setPage(data.page || 1)
      setTotalPages(data.total_pages || 1)
      setTotalResults(data.total_results || (data.results || []).length)
      if (!(data.results || []).length) {
        setNotice('没有找到匹配的影视内容，可以换个关键词试试')
      }
    } catch (err) {
      setError(err.message)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const loadMoreSearch = async () => {
    if (loadingMore || loading || page >= totalPages || !keyword.trim()) return

    const nextPage = page + 1
    setLoadingMore(true)
    setError('')
    try {
      const data = await apiRequest(`/public/tmdb/search?q=${encodeURIComponent(keyword.trim())}&page=${nextPage}`)
      setResults((prev) => [...prev, ...(data.results || [])])
      setPage(data.page || nextPage)
      setTotalPages(data.total_pages || totalPages)
      setTotalResults(data.total_results || totalResults)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoadingMore(false)
    }
  }

  const loadMoreWishList = async () => {
    if (loadingWishListMore || loadingWishList || wishPage >= wishTotalPages) return

    const nextPage = wishPage + 1
    setLoadingWishListMore(true)
    setWishListError('')
    try {
      const data = await apiRequest(`/public/wishes?page=${nextPage}&page_size=20`)
      setWishList((prev) => [...prev, ...(data.requests || []).map(normalizeWishItem)])
      setWishPage(data.page || nextPage)
      setWishTotalPages(data.total_pages || wishTotalPages)
      setWishTotalResults(data.total_results || wishTotalResults)
    } catch (err) {
      setWishListError(err.message)
    } finally {
      setLoadingWishListMore(false)
    }
  }

  const showSeasonDetail = async (item) => {
    setSeasonDetailItem(item)
    setSeasonDetailOpen(true)
    setSeasonDetailLoading(true)
    setSeasonDetailSeasons([])
    try {
      const data = await apiRequest(`/public/tmdb/seasons?tmdb_id=${item.tmdb_id}`)
      setSeasonDetailSeasons(data.seasons || [])
    } catch (err) {
      setSeasonDetailSeasons([])
    } finally {
      setSeasonDetailLoading(false)
    }
  }

  const submitSeasonWish = async (season, parentItem) => {
    const submitKey = `season-${parentItem.tmdb_id}-${season.season_number}`
    setSubmittingId(submitKey)
    setError('')
    setNotice('')
    try {
      const item = {
        tmdb_id: parentItem.tmdb_id,
        media_type: 'tv',
        title: `${parentItem.title} - ${season.name}`,
        original_title: parentItem.original_title,
        release_date: season.air_date,
        year: season.air_date ? season.air_date.slice(0, 4) : '',
        overview: '',
        poster_path: season.poster_path,
        poster_url: season.poster_url,
        backdrop_path: '',
        backdrop_url: '',
      }
      const data = await apiRequest('/public/wishes', {
        method: 'POST',
        body: JSON.stringify({ item }),
      })
      setNotice(data.message || `${season.name} 已加入想看清单`)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmittingId('')
    }
  }

  const submitWish = async (item) => {
    const submitKey = `${item.media_type}-${item.tmdb_id}`
    setSubmittingId(submitKey)
    setError('')
    setNotice('')
    setWishListError('')
    try {
      const data = await apiRequest('/public/wishes', {
        method: 'POST',
        body: JSON.stringify({ item }),
      })
      const requestRecord = data.request ? normalizeWishItem(data.request) : null
      setNotice(data.message || '已加入想看清单')
      setResults((prev) =>
        prev.map((current) =>
          current.tmdb_id === item.tmdb_id && current.media_type === item.media_type
            ? {
                ...current,
                requested: true,
                request_id: data.request?.id,
                request_status: data.request?.status || 'pending',
              }
            : current
        )
      )

      if (requestRecord && wishListOpen) {
        setWishList((prev) => {
          const exists = prev.some((current) => current.tmdb_id === requestRecord.tmdb_id && current.media_type === requestRecord.media_type)
          if (exists) {
            return prev.map((current) =>
              current.tmdb_id === requestRecord.tmdb_id && current.media_type === requestRecord.media_type
                ? { ...current, ...requestRecord }
                : current
            )
          }
          return [requestRecord, ...prev]
        })
        if (data.request?.created) {
          setWishTotalResults((prev) => prev + 1)
        }
      }
    } catch (err) {
      if (wishListOpen) {
        setWishListError(err.message)
      } else {
        setError(err.message)
      }
    } finally {
      setSubmittingId('')
    }
  }

  if (!open) return null

  return (
    <>
      <div className='fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4' onClick={onClose}>
        <Card className='flex max-h-[90vh] w-full max-w-7xl flex-col overflow-hidden' onClick={(e) => e.stopPropagation()}>
          <CardHeader className='shrink-0 border-b pb-4'>
            <div className='flex items-start justify-between gap-4'>
              <div>
                <CardTitle>用户求片</CardTitle>
                <p className='mt-1 text-sm text-muted-foreground'>
                  输入关键词后会从 TMDB 搜索电影/电视剧，点击海报即可加入想看清单。
                </p>
                {totalResults ? <p className='mt-1 text-xs text-muted-foreground'>共找到 {totalResults} 条结果</p> : null}
              </div>
              <Button size='icon' variant='ghost' onClick={onClose} title='关闭'>
                <X className='h-4 w-4' />
              </Button>
            </div>
          </CardHeader>
          <CardContent className='flex min-h-0 flex-1 flex-col gap-4 p-6'>
            <form className='flex shrink-0 flex-col gap-2 sm:flex-row' onSubmit={onSearch}>
              <Input
                placeholder='例如：流浪地球、黑镜、鱿鱼游戏'
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
              />
              <Button type='submit' disabled={loading}>
                {loading ? <LoaderCircle className='mr-2 h-4 w-4 animate-spin' /> : <Search className='mr-2 h-4 w-4' />}
                搜索
              </Button>
              <Button
                type='button'
                variant='outline'
                onClick={() => {
                  setWishListOpen(true)
                }}
              >
                <Heart className='mr-2 h-4 w-4' /> 已求列表
              </Button>
            </form>

            {error ? <div className='shrink-0 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive'>{error}</div> : null}
            {notice ? <div className='shrink-0 rounded-md border border-primary/30 bg-primary/5 p-3 text-sm text-primary'>{notice}</div> : null}
            {loading ? <p className='shrink-0 text-sm text-muted-foreground'>正在搜索 TMDB...</p> : null}

            <div className='min-h-0 flex-1 overflow-y-auto pr-1'>
              <div className='grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5'>
                {results.map((item) => (
                  <WishPosterCard key={`${item.media_type}-${item.tmdb_id}-search`} item={item} submittingId={submittingId} onSubmit={submitWish} onShowSeasonDetail={showSeasonDetail} />
                ))}
              </div>

              {!loading && !results.length ? <p className='py-8 text-center text-sm text-muted-foreground'>请输入关键词开始搜索</p> : null}
            </div>

            {!loading && results.length && page < totalPages ? (
              <div className='flex shrink-0 justify-center'>
                <Button type='button' variant='outline' onClick={loadMoreSearch} disabled={loadingMore}>
                  {loadingMore ? <LoaderCircle className='mr-2 h-4 w-4 animate-spin' /> : <ChevronDown className='mr-2 h-4 w-4' />}
                  {loadingMore ? '加载中...' : '加载更多'}
                </Button>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <WishListModal
        open={wishListOpen}
        onClose={() => setWishListOpen(false)}
        items={wishList}
        loading={loadingWishList}
        loadingMore={loadingWishListMore}
        error={wishListError}
        totalResults={wishTotalResults}
        page={wishPage}
        totalPages={wishTotalPages}
        submittingId={submittingId}
        onSubmit={submitWish}
        onLoadMore={loadMoreWishList}
        onShowSeasonDetail={showSeasonDetail}
      />

      <SeasonDetailModal
        open={seasonDetailOpen}
        onClose={() => setSeasonDetailOpen(false)}
        item={seasonDetailItem}
        loading={seasonDetailLoading}
        seasons={seasonDetailSeasons}
        librarySeasonCount={seasonDetailItem?.library_season_count}
        onSubmitSeason={submitSeasonWish}
      />
    </>
  )
}

function ActiveSessionCard({ session }) {
  return (
    <Card className='overflow-hidden transition-all hover:shadow-md'>
      <CardContent className='p-4'>
        <div className='flex items-start gap-3'>
          <div className='relative flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary/20 to-primary/10'>
            <div className='absolute inset-0 rounded-xl bg-gradient-to-br from-primary/10 to-transparent' />
            <Play className='relative z-10 h-6 w-6 text-primary' />
          </div>
          <div className='flex-1 min-w-0'>
            <div className='font-medium'>{session.username}</div>
            <div className='mt-1 text-sm text-muted-foreground truncate'>{session.media}</div>
            <div className='mt-2 flex items-center gap-2 text-xs text-muted-foreground'>
              <span className='truncate'>{session.device}</span>
              <span>·</span>
              <span className='truncate'>{session.client}</span>
            </div>
          </div>
        </div>
        <div className='mt-3 border-t border-border' />
        <div className='mt-3 flex justify-between gap-2 text-xs'>
          <span className='text-muted-foreground shrink-0'>IP: {session.ip_address}</span>
          <span className='text-primary truncate'>{session.location}</span>
        </div>
      </CardContent>
    </Card>
  )
}

export default function HomePage() {
  const [username, setUsername] = useState('')
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(false)
  const [requestOpen, setRequestOpen] = useState(false)
  const [userSearchOpen, setUserSearchOpen] = useState(false)
  const fingerprintRef = useRef('')
  const navigate = useNavigate()

  const onUserSearch = (event) => {
    event.preventDefault()
    if (!username) return
    setUserSearchOpen(false)
    navigate(`/search?username=${encodeURIComponent(username)}`)
  }

  useEffect(() => {
    let active = true
    let timer = null

    const load = async (showLoading = false) => {
      if (!active) return
      if (showLoading) setLoading(true)
      try {
        const data = await apiRequest('/public/active-sessions')
        const next = (data.sessions || []).slice().sort((a, b) => String(a.session_id).localeCompare(String(b.session_id)))
        const fingerprint = JSON.stringify(
          next.map((session) => ({
            session_id: session.session_id,
            user_id: session.user_id,
            username: session.username,
            groups: session.groups,
            ip_address: session.ip_address,
            location: session.location,
            device: session.device,
            client: session.client,
            media: session.media,
          }))
        )
        if (active && fingerprint !== fingerprintRef.current) {
          setSessions(next)
          fingerprintRef.current = fingerprint
        }
      } catch {
        if (active && showLoading) {
          setSessions([])
          fingerprintRef.current = ''
        }
      } finally {
        if (active && showLoading) setLoading(false)
      }
    }

    load(true)
    timer = setInterval(() => load(false), 5000)

    return () => {
      active = false
      if (timer) clearInterval(timer)
    }
  }, [])

  const sessionCountText = useMemo(() => `当前正在播放（${sessions.length}）`, [sessions.length])

  return (
    <>
      <div className='mx-auto max-w-6xl space-y-6 p-4 pb-8 md:p-8'>
        <div className='flex flex-wrap items-center justify-between gap-3'>
          <div>
            <h1 className='text-2xl font-bold'>EmbyQ用户自助中心</h1>
            <p className='mt-1 text-sm text-muted-foreground'>Emby 个人播放记录查询、封禁查询，也可以直接搜索影视内容，加入公共求片清单。</p>
          </div>
        </div>

        <div className='flex gap-2'>
          <Button onClick={() => setUserSearchOpen(true)}>
            <Search className='mr-2 h-4 w-4' /> 用户查询
          </Button>
          <Button onClick={() => setRequestOpen(true)}>
            <Heart className='mr-2 h-4 w-4' /> 求片
          </Button>
        </div>

        <div className='space-y-4'>
          <div className='flex items-center justify-between'>
            <h2 className='text-lg font-semibold'>{sessionCountText}</h2>
            {sessions.length > 0 ? (
              <Badge variant='secondary' className='text-xs'>
                {sessions.length} 人
              </Badge>
            ) : null}
          </div>

          {loading ? (
            <div className='text-center py-8 text-sm text-muted-foreground'>加载中...</div>
          ) : sessions.length > 0 ? (
            <div className='grid gap-4 md:grid-cols-2 lg:grid-cols-3'>
              {sessions.map((session) => (
                <ActiveSessionCard key={session.session_id} session={session} />
              ))}
            </div>
          ) : (
            <Card>
              <CardContent className='py-8 text-center text-sm text-muted-foreground'>
                暂无正在播放
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      <RequestModal open={requestOpen} onClose={() => setRequestOpen(false)} />

      <Dialog open={userSearchOpen} onClose={() => setUserSearchOpen(false)} size='lg'>
        <DialogClose onClose={() => setUserSearchOpen(false)} />
        <DialogHeader>
          <DialogTitle>用户查询</DialogTitle>
          <DialogDescription>输入 Emby 用户名查询播放记录</DialogDescription>
        </DialogHeader>
        <form className='flex gap-2 mt-4' onSubmit={onUserSearch}>
          <Input
            placeholder='输入 Emby 用户名'
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
          />
          <Button type='submit'>查询</Button>
        </form>
      </Dialog>
    </>
  )
}
