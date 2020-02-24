# -*- incoding:utf-8 -*-
import random
import re
import datetime
import pymongo
import requests
from lxml import etree
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait


class tiebaScraper():
    def __init__(self,url):
        print("初始化中...")
        profile_path = r'C:\Users\szzhanga\AppData\Roaming\Mozilla\Firefox\Profiles\csu7hedv.default-release-1578623880884'
        profile = webdriver.FirefoxProfile(profile_path)
        firefox_opptions = webdriver.FirefoxOptions()
        firefox_opptions.add_argument('-headless')
        driver = webdriver.Firefox(profile, options=firefox_opptions)
        self.url = url
        driver.get(self.url)

        # get cookies from driver
        cookies = driver.get_cookies()

        session = requests.session()

        # put cookies into session's cookie
        for c in cookies:
            requests.utils.add_dict_to_cookiejar(session.cookies, {c['name']: c['value']})

        # exchange cookies into dict
        cookie = requests.utils.dict_from_cookiejar(session.cookies)

        self.cookie = str(cookie)
        self.session = requests.session()
        self.driver=driver
        self.mgclient=pymongo.MongoClient("mongodb://localhost:27017/")
        self.timeOut=3
        self.PROXY_POOL_URL = 'http://localhost:5555/random'
        print("初始化完成。。。")
    def get_proxy(self):
        try:
            response = requests.get(self.PROXY_POOL_URL)
            if response.status_code == 200:
                return response.text
        except ConnectionError:
            return None

    def get_page_urls(self, url, key, size):
        print("获取page_urls中...")
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:71.0) Gecko/20100101 Firefox/71.0'
        headers = {
            # pretend to be one browser
            'User-Agent': user_agent,
            'Cookie': self.cookie
        }

        url0 = url % (key, 0)
        r = self.session.get(url0)

        text = r.text

        html = etree.HTML(text)
        tail = html.xpath('//a[@class="last pagination-item "]/@href')

        href_value = tail[0]
        pn = re.compile(r'pn=(\d+)')
        search = pn.search(href_value)
        total = 0
        if search:
            total = search.group(1)
            print("总共有%s条记录"%total)
        else:
            print("not found total records")

        pgn = int(total) // size
        purls = []
        for n in range(pgn):
            pn = n * size
            hurl = url % (key, pn)
            purls.append(hurl)
        print("获取page_urls完成。。。")
        return purls

    # save pcodes into mongodb
    def save_to_mongodb(self,pcodes):
        print("存储pcodes中...")
        # create sites database
        tdb = self.mgclient['sites']

        # create tieba set
        tset = tdb['tieba']
        local_plist=[]
        for al in tset.find({}, {'_id': 0, 'p_code': 1,'reply': 1}):
            local_plist.append(al['p_code'])

        inlist=[]

        for p in pcodes:
            if p not in local_plist:
                inlist.append(p)

        if len(inlist)==0:
            print("没有新增数据...")
            return inlist
        else:
            print("新增了%d条数据"%len(inlist))

        dict_many = []

        while len(dict_many) < len(inlist):
            for l in inlist:
                dict_base = {'p_code': l,'reply': 0}
                dict_many.append(dict_base)

        # insert into mongodb
        tset.insert_many(dict_many)
        print("存储pcodes完成。。。")
        return inlist

    #filter pcodes
    def filter_pcodes(self,ptdict):
        pn=re.compile(r'鸡眼|帮|怎么|看看|疼|什么|疣|拜托|痛|除|办法|治|告诉|求助')
        ptlist=[]
        for k in ptdict.keys():
            #print(ptdict[k])
            if pn.search(ptdict[k]):
                ptlist.append(k)
        return ptlist

    # get pcodes from page_usrls
    def get_pcodes(self, purls):
        print("获取pcodes中...")
        pcodes = []
        for url in purls:
            # wait random times
            time.sleep(random.randint(0,3))

            r = requests.get(url)
            text = r.text
            html = etree.HTML(text, etree.HTMLParser())

            # get p/xxxxxx from each div
            codes = html.xpath('//div[@class="threadlist_title pull_left j_th_tit "]/a/@href')
            titles= html.xpath('//div[@class="threadlist_title pull_left j_th_tit "]/a/@title')
            joined_ps = ",".join(codes)
            plist = joined_ps.split(",")
            joined_ts = ",".join(titles)
            tlist = joined_ts.split(",")

            pt_dict=dict(zip(plist,tlist))
            ptlist=self.filter_pcodes(pt_dict)
            # remove repeated ps
            pcodes.extend(ptlist)
        print("获取pcodes完成。。。")
        return pcodes

    # get url for each owner
    def get_aim_urls(self, pcodes):
        print("组装aim_urls中...")
        urls = []
        prefix = 'https://tieba.baidu.com'
        for p in pcodes:
            urls.append(prefix + p)
        print("组装aim_url完成。。。")
        return urls

    # create one reply for owner
    def create_random_reply(self):
        reply_list=[
            '你好，在哪里可以下载全本小说啊？',
            '你好，有免费小说吗？求推荐！',
            '你好，还有同类型的小说吗？求推荐！',
            '你好，我也是斗破迷，能加个好友吗？'
        ]
        rdm=random.randint(0, len(reply_list)-1)
        return reply_list[rdm]

    # delete replies of owner
    def delete_reply(self,aim_urls):
        print("删除回复中...")
        for url in aim_urls:
            self.driver.get(url)
            try:
                tail_page = WebDriverWait(self.driver, self.timeOut).until(
                    expected_conditions.element_to_be_clickable((By.LINK_TEXT, '尾页')))
            except:
                print("%s找不到尾页"%url)
            else:
                tail_page.click()
            finally:
                pass

            try:
                reply = WebDriverWait(self.driver, self.timeOut).until(
                    expected_conditions.element_to_be_clickable((By.XPATH, '//*[@id="quick_reply"]')))
            except:
                raise Exception("%s找不到回复"%url)
            else:
                reply.click()
                self.driver.execute_script("window.scrollTo(0,document.body.scrollHeight)")

            try:
                delete = WebDriverWait(self.driver, self.timeOut).until(
                    expected_conditions.element_to_be_clickable((By.LINK_TEXT, '删除')))
            except:
                print("%s找不到删除"%url)
            else:
                delete.click()
            finally:
                pass

            try:
                sure = WebDriverWait(self.driver, self.timeOut).until(
                    expected_conditions.element_to_be_clickable((By.CSS_SELECTOR, ".dialogJbtn:nth-child(1)")))
            except:
                print("%s找不到确定" % url)
            else:
                sure.click()
            finally:
                print("%s删除完成。。。" % url)

        print("删除回复完成。。。")

    # scroll page to aim element
    def scroll_element(self,locator):
        n=0
        while True:
            try:
                print("定位1楼中...")
                top_one=WebDriverWait(self.driver,self.timeOut).until(
                    expected_conditions.presence_of_element_located((By.XPATH,locator)))
            except:
                # scroll one page
                print("没有找到1楼,往下滑1页")
                page_start=n*528
                page_end=(n+1)*528
                self.driver.execute_script("window.scrollTo(%d,%d)"%(page_start,page_end))
                time.sleep(self.timeOut)
                n+=1
                if n>=5:
                    break
            else:
                print("找到1楼。。。")
                self.driver.execute_script("arguments[0].scrollIntoView();", top_one)
                break

    # reply for owner
    def reply_owner(self, aim_urls):
        print("回复owners中...")
        for url in aim_urls:
            print("当前的url是：%s"%url)
            self.driver.get(url)
            self.driver.maximize_window()
            time.sleep(3)
            while True:
                try:
                    locate="//span[contains(text(),'1楼')]"
                    self.scroll_element(locate)
                except:
                    print("没有滑到1楼")

                try:
                    date=WebDriverWait(self.driver,self.timeOut).until(
                        expected_conditions.visibility_of_element_located((By.CSS_SELECTOR,'.p_tail > li:nth-child(2) > span:nth-child(1)')))
                except:
                    print("没有找到日期")
                else:
                    text_str=date.text
                    print(text_str)
                    date_now=datetime.datetime.now()
                    expire_days=730
                    t1 = datetime.timedelta(days=expire_days)
                    diff=date_now-t1

                    diff_str=datetime.datetime.strftime(diff,'%Y-%m-%d %H:%M')
                    # if time expired then break
                    if text_str < diff_str:
                        print("过期不候")
                        break

                try:
                    reply = WebDriverWait(self.driver, self.timeOut).until(
                        expected_conditions.element_to_be_clickable((By.XPATH, "//a[@class='p_reply_first']")))
                except:
                    print("找不到回复")
                else:
                    try:
                        reply.click()
                    except:
                        print("回复不可点击，跳过！")
                        break

                try:
                    self.driver.execute_script("window.scrollTo(0,document.body.scrollHeight)")
                except:
                    print('窗口没有滚动到底部')

                try:
                    WebDriverWait(self.driver,self.timeOut).until(expected_conditions.element_to_be_clickable((By.ID,'ueditor_replace'))).click()
                    time.sleep(self.timeOut)
                    ueditor = self.create_random_reply()
                    element = WebDriverWait(self.driver, self.timeOut).until(expected_conditions.presence_of_element_located((By.ID, "ueditor_replace")))
                    js = "if(arguments[0].contentEditable === 'true') {arguments[0].innerText = 'replyContents'}".replace(r'replyContents', ueditor)
                    self.driver.execute_script(js, element)
                except:
                    print('内容没有编辑')

                try:
                    submit = WebDriverWait(self.driver, self.timeOut).until(
                        expected_conditions.element_to_be_clickable((By.LINK_TEXT, '发 表')))
                except:
                    print("发表没有找到")
                else:
                    submit.click()

                try:
                    success = WebDriverWait(self.driver, self.timeOut).until(expected_conditions.visibility_of_element_located(
                        (By.XPATH, "//div[@class='post_success_tip']")))
                except:
                    print("success not appeared")
                else:
                    suctext = success.text
                    if suctext.strip() == '发表成功！':
                        # exchange the reply into 1
                        self.exchange_status(url)
                        break
        print("回复owners完成。。。")

    # update status from 0 to 1
    def exchange_status(self,url):
        pn = re.compile(r'(/p/\d+)')
        search = pn.search(url)
        if search:
            ps = search.group(1)
        else:
            print("p_string not matched")

        tdb = self.mgclient['sites']
        tset = tdb['tieba']
        local_plist = []
        for al in tset.find({}, {'_id': 0, 'p_code': 1, 'reply': 1}):
            local_plist.append(al)

        pr={}
        prlist=[]
        for l in local_plist:
            pr={l['p_code']:l['reply']}
            prlist.append(pr)

        for p in prlist:
            if ps in p.keys():
                if p[ps]==0:
                    print("%s没有回复"%ps)
                    # update 0 to 1 in mongodb
                    ov={'p_code':ps,'reply':0}
                    nv={"$set":{'p_code':ps,'reply':1}}
                    tset.update_one(ov,nv)
                else:
                    print("%s已经回复"%ps)
if __name__ == '__main__':
    print("Make sure you have logged in aim address manully ~")
    # url_base=input("Please input your base address:")
    # keyWords=input("Please input your key words:")
    keyWords = '鸡眼'
    size = 50
    url_base = 'https://tieba.baidu.com/f?kw=%s&ie=utf-8&pn=%d'

    url_init = url_base%(keyWords,size)
    # Init the tiebaScraper
    ts = tiebaScraper(url_init)

    # get page urls
    page_urls = ts.get_page_urls(url_base, keyWords, size)

    # get pcodes from page urls
    pcodes = ts.get_pcodes(page_urls)

    # save pcodes those not in mongodb and return them
    inplist=ts.save_to_mongodb(pcodes)

    # get aim urls according pcodes
    aim_urls = ts.get_aim_urls(inplist)

    #delete record from aim_urls
    #ts.delete_reply(aim_urls)

    #reply contents to aim urls
    ts.reply_owner(aim_urls)
