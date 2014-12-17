import threading
import datetime
import sys
import time


class Progress(object):
    def __init__(self, crawl_type, crawl_count, total_count):
        self.crawl_type = crawl_type
        self.crawl_count = crawl_count
        self.total_count = total_count
        self.parse_count = 0
        self.preloaded = 0
        self.timer_close_event = None
        self.timer_thread = None

    def output(self, remaining):
        elapsed = time.time() - self.start_time
        elapsed_str = str(datetime.timedelta(seconds=int(elapsed)))
        sys.stdout.write("\r" + " " * 100 + "\r")
        msg = "{} {} - {}/{} (elapsed {}, {})"
        sys.stdout.write(msg.format(self.crawl_type,
                                    self.crawl_count,
                                    self.parse_count,
                                    self.total_count,
                                    elapsed_str,
                                    remaining))
        sys.stdout.flush()

    def progress(self):
        while not self.timer_close_event.wait(1):
            try:
                elapsed = time.time() - self.start_time
                remaining = float(self.total_count - self.parse_count) / \
                            (float(self.parse_count - self.preloaded) / float(elapsed))
                remaining = str(datetime.timedelta(seconds=int(remaining)))
                remaining = "est. " + remaining
            except:
                remaining = "calculating time remaining"
            self.output(remaining)
        self.output("finished")
        print

    def start(self):
        self.start_time = time.time()
        self.timer_close_event = threading.Event()
        self.timer_thread = threading.Thread(target=self.progress)
        self.timer_thread.daemon = True
        self.timer_thread.start()

    def stop(self):
        self.timer_close_event.set()
        self.timer_thread.join()
