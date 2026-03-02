#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Date    : 2019-06-11 23:44:26
# @Author  : Kelly Hwong (dianhuangkan@gmail.com)
# @Link    : https://github.com/KellyHwong/ip138
# @Version : $0.0.0$

import requests
from bs4 import BeautifulSoup
from ip138.constant import HEADERS


def ip138(ip):
    '''
    ip138 IP geometry infomation API
    改用 ipshudi.com 获取 IP 归属地信息
    :@param ip (str): query ip address (str)
    :@return (dict): 
    '''
    url = "https://www.ipshudi.com/%s.htm" % ip
    query_html = requests.get(url, headers=HEADERS, timeout=10).content
    query_html = query_html.decode("utf-8")
    query_soup = BeautifulSoup(query_html, "lxml")
    
    ret = dict()
    
    # 查找表格中的 IP 信息
    table = query_soup.find("table")
    if table:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                # 清理 value 中的多余文本
                value = value.replace("上报纠错", "").replace("Ping", "").strip()
                ret[key] = value
    
    # 检查是否获取到了归属地信息，如果没有可能是DNS列表页面
    if "归属地" not in ret:
        # 尝试从页面标题或其他元素获取信息
        title = query_soup.find('title')
        if title:
            ret['页面标题'] = title.get_text(strip=True)
        ret['提示'] = '该IP可能是公共DNS，未找到归属地信息'
    
    return ret
