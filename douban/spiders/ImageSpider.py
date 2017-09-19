# /usr/bin/env python
# encoding=utf-8
import datetime
import random
import re
import time

import os
import scrapy
from pybloom import BloomFilter

from douban.component import DBComponent
from douban.items import ImageItem


class ImageSpider(scrapy.Spider):
    name = "imageSpider"
    boolmPath = "./douban_bloom_filter"

    def __init__(self, name=None, **kwargs):
        super(ImageSpider, self).__init__(name, **kwargs)
        is_exist = os.path.exists(ImageSpider.boolmPath)
        if not is_exist:
            ImageSpider.boolm_filter = BloomFilter(1000000, 0.001)
        else:
            boolm_file = open(ImageSpider.boolmPath, 'r')
            try:
                ImageSpider.boolm_filter = BloomFilter.fromfile(boolm_file)
            except BaseException:
                ImageSpider.boolm_filter = BloomFilter(1000000, 0.001)
            finally:
                boolm_file.close()

    def start_requests(self):
        # group_list = ['https://www.douban.com/group/368133/']
        group_list = DBComponent.getAllGroup()
        random.shuffle(group_list)
        for url in group_list:
            yield scrapy.Request(url=url + "discussion?start=0", callback=self.parse_group)
            # yield scrapy.Request(url=url + "discussion?start=50", callback=self.parse_group)

    def parse_group(self, response):
        tr_list = response.css("table.olt tr:not(:first-child)")
        group_url = re.sub("discussion.*", "", response.url)
        tr_index = 0
        for tr in tr_list:
            url = tr.css("td.title a::attr(href)").extract_first()
            try:
                reply_time = tr.css("td.time::text").extract_first()
                reply_time = time.strptime(reply_time, "%m-%d %H:%M")  # 解析回复时间
                reply_month = reply_time.tm_mon
                reply_day = reply_time.tm_mday
                reply_time_min = datetime.date.today() + datetime.timedelta(-3)  # 获取当前时间-2天的时间
                reply_month_min = reply_time_min.month
                reply_day_min = reply_time_min.day
                tr_index += 1
            except BaseException, e:
                DBComponent.deleteGroup(group_url)
                break
            # 查找回复时间>2天的
            if (reply_month > reply_month_min) or (reply_month == reply_month_min and reply_day >= reply_day_min):
                is_exist = ImageSpider.boolm_filter.add(url)
                # print 'is_exist', is_exist
                if not is_exist:
                    yield scrapy.Request(url=url, callback=self.parse_content)
            elif tr_index == 1:
                DBComponent.deleteGroup(group_url)

    def parse_content(self, response):
        download_flag = False
        topic_content = response.css(".topic-doc .topic-content")
        for content in topic_content.css("p::text").extract():
            content = content.encode("utf-8")
            if re.search("(微信群|群)", content):
                print response.url, content
                download_flag = True
                break
        if download_flag:
            group_url = response.css(".title.title ::attr(href)").extract_first()
            group_url = re.sub('\\?.*$', '', group_url)
            DBComponent.addGroupMatch(group_url)
            image_item = ImageItem()
            image_item["image_urls"] = topic_content.css("img::attr(src)").extract()
            return image_item

    @staticmethod
    def close(spider, reason):
        boolm_file = open(ImageSpider.boolmPath, 'a')
        ImageSpider.boolm_filter.tofile(boolm_file)
        boolm_file.close()
        return super(ImageSpider, spider).close(spider, reason)
