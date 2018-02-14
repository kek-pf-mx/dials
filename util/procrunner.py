from __future__ import absolute_import, division
from multiprocessing import Pipe
import select
from cStringIO import StringIO
import subprocess
import time
import timeit
from threading import Thread
'''Function to run an external process, print and retain stdout and stderr,
   enforce a timeout, keep the exit code, etc.'''

dummy = False

class _LineAggregator:
  '''Buffer that can be filled with stream data and will aggregate complete
     lines. Lines can be printed or passed to an arbitrary callback function.
     The lines passed to the callback function do not contain a trailing
     newline character.'''

  def __init__(self, print_line=False, callback=None):
    '''Create aggregator object.'''
    self._buffer = ''
    self._print = print_line
    self._callback = callback

  def add(self, data):
    '''Add a single character to buffer. If one or more full lines are found,
       print them (if desired) and pass to callback function.'''
    self._buffer += data
    if "\n" in data:
      to_print, remainder = self._buffer.rsplit('\n')
      if self._print:
        print to_print
      if self._callback:
        self._callback(to_print)
      self._buffer = remainder

  def flush(self):
    '''Print/send any remaining data to callback function.'''
    if self._buffer:
      if self._print:
        print self._buffer
      if self._callback:
        self._callback(self._buffer)
    self._buffer = ''

class _NonBlockingStreamReader:
  '''Reads a stream in a thread to avoid blocking/deadlocks'''

  def __init__(self, stream, output=True, debug=False, notify=None, callback=None):
    '''Creates and starts a thread which reads from a stream.'''
    self._buffer = StringIO()
    self._closed = False
    self._closing = False
    self._debug = debug
    self._stream = stream
    self._terminated = False

    def _thread_write_stream_to_buffer():
      la = _LineAggregator(print_line=output, callback=callback)
      char = True
      while char:
        if select.select([self._stream], [], [], 0.1)[0]:
          char = self._stream.read(1)
          if char:
            self._buffer.write(char)
            la.add(char)
        else:
          if self._closing: break
      self._terminated = True
      la.flush()
      if self._debug:
        print "Stream reader terminated"
      if notify:
        notify()

    self._thread = Thread(target=_thread_write_stream_to_buffer)
    self._thread.daemon = True
    self._thread.start()

  def has_finished(self):
    '''Returns whether the thread reading from the stream is still alive.'''
    return self._terminated

  def get_output(self):
    '''Retrieve the stored data in full.
       This call may block if the reading thread has not yet terminated.'''
    self._closing = True
    if not self.has_finished():
      if self._debug:
        underrun_debug_timer = timeit.default_timer()
        print "NBSR underrun" # Main thread overtook stream reading thread.
      self._thread.join()
      if not self.has_finished():
        if self._debug:
          print "NBSR join after %f seconds, underrun not resolved" % (timeit.default_timer() - underrun_debug_timer)
        raise Exception('thread did not terminate')
      if self._debug:
        print "NBSR underrun resolved after %f seconds" % (timeit.default_timer() - underrun_debug_timer)
    if self._closed:
      raise Exception('streamreader double-closed')
    self._closed = True
    data = self._buffer.getvalue()
    self._buffer.close()
    return data

class _NonBlockingStreamWriter:
  '''Writes to a stream in a thread to avoid blocking/deadlocks'''

  def __init__(self, stream, data, debug=False, notify=None):
    '''Creates and starts a thread which writes data to stream.'''
    self._buffer = data
    self._buffer_len = len(data)
    self._buffer_pos = 0
    self._debug = debug
    self._max_block_len = 4096
    self._stream = stream
    self._terminated = False

    def _thread_write_buffer_to_stream():
      while self._buffer_pos < self._buffer_len:
        if (self._buffer_len - self._buffer_pos) > self._max_block_len:
          block = self._buffer[self._buffer_pos:(self._buffer_pos + self._max_block_len)]
        else:
          block = self._buffer[self._buffer_pos:]
        try:
          self._stream.write(block)
        except IOError as e:
          if e.errno == 32: # broken pipe, ie. process terminated without reading entire stdin
            self._stream.close()
            self._terminated = True
            if notify:
              notify()
            return
          raise
        self._buffer_pos += len(block)
        if debug:
          print "wrote %d bytes to stream" % len(block)
      self._stream.close()
      self._terminated = True
      if notify:
        notify()

    self._thread = Thread(target=_thread_write_buffer_to_stream)
    self._thread.daemon = True
    self._thread.start()

  def has_finished(self):
    '''Returns whether the thread writing to the stream is still alive.'''
    return self._terminated

  def bytes_sent(self):
    '''Return the number of bytes written so far.'''
    return self._buffer_pos

  def bytes_remaining(self):
    '''Return the number of bytes still to be written.'''
    return self._buffer_len - self._buffer_pos

def run_process(command,
                timeout=None,
                debug=False,
                stdin=None,
                print_stdout=True,
                print_stderr=True,
                callback_stdout=None,
                callback_stderr=None,
                environ=None):
  '''run an external process, command line specified as array,
     optionally enforces a timeout specified in seconds, obtains STDOUT,
     STDERR and exit code and returns summary dictionary. Optionally can
     overload environment variables in the subprocess, in addition to
     os.environ.'''

  time_start = time.strftime("%Y-%m-%d %H:%M:%S GMT", time.gmtime())
  if debug:
    print "Starting external process:", command

  if stdin is None:
    stdin_pipe = None
  else:
    stdin_pipe = subprocess.PIPE

  if dummy:
    return {
        'exitcode': 0, 'command': command, 'stdout': '', 'stderr': '', 'timeout': False, 'runtime': 0, 'time_start':
        time_start, 'time_end': time_start
    }

  start_time = timeit.default_timer()
  if timeout is not None:
    max_time = start_time + timeout

  if environ:
    import os, copy
    env = copy.copy(os.environ)
    env.update(environ)
  else:
    env = environ

  p = subprocess.Popen(command, shell=False, stdin=stdin_pipe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

  thread_pipe_pool = []
  notifyee, notifier = Pipe(False)
  thread_pipe_pool.append(notifyee)
  stdout = _NonBlockingStreamReader(
      p.stdout, output=print_stdout, debug=debug, notify=notifier.close, callback=callback_stdout)
  notifyee, notifier = Pipe(False)
  thread_pipe_pool.append(notifyee)
  stderr = _NonBlockingStreamReader(
      p.stderr, output=print_stderr, debug=debug, notify=notifier.close, callback=callback_stderr)
  if stdin is not None:
    notifyee, notifier = Pipe(False)
    thread_pipe_pool.append(notifyee)
    stdin = _NonBlockingStreamWriter(p.stdin, data=stdin, debug=debug, notify=notifier.close)

  timeout_encountered = False

  while (p.returncode is None) and \
        ((timeout is None) or (timeit.default_timer() < max_time)):
    if debug and timeout is not None:
      print "still running (T%.2fs)" % (timeit.default_timer() - max_time)

    # wait for some time or until a stream is closed
    try:
      if thread_pipe_pool:
        # Wait for up to 0.5 seconds or for a signal on a remaining stream,
        # which could indicate that the process has terminated.
        event = thread_pipe_pool[0].poll(0.5)
        if event:
          # One-shot, so remove stream and watch remaining streams
          thread_pipe_pool.pop(0)
          if debug:
            print "Event received from stream thread"
      else:
        time.sleep(0.5)
    except KeyboardInterrupt:
      p.kill() # if user pressed Ctrl+C we won't be able to produce a proper report anyway
      # but at least make sure the child process dies with us
      raise

    # check if process is still running
    p.poll()

  if p.returncode is None:
    # timeout condition
    timeout_encountered = True
    if debug:
      print "timeout (T%.2fs)" % (timeit.default_timer() - max_time)

    # send terminate signal and wait some time for buffers to be read
    p.terminate()
    if thread_pipe_pool:
      thread_pipe_pool[0].poll(0.5)
    if not stdout.has_finished() or not stderr.has_finished():
      time.sleep(2)
    p.poll()

  if p.returncode is None:
    # thread still alive
    # send kill signal and wait some more time for buffers to be read
    p.kill()
    if thread_pipe_pool:
      thread_pipe_pool[0].poll(0.5)
    if not stdout.has_finished() or not stderr.has_finished():
      time.sleep(5)
    p.poll()

  if p.returncode is None:
    raise RuntimeError("Process won't terminate")

  runtime = timeit.default_timer() - start_time
  if debug:
    if timeout is not None:
      print "Process ended after %.1f seconds with exit code %d (T%.2fs)" % \
        (runtime, p.returncode, timeit.default_timer() - max_time)
    else:
      print "Process ended after %.1f seconds with exit code %d" % \
        (runtime, p.returncode)

  stdout = stdout.get_output()
  stderr = stderr.get_output()
  time_end = time.strftime("%Y-%m-%d %H:%M:%S GMT", time.gmtime())

  result = {
      'exitcode': p.returncode, 'command': command, 'stdout': stdout, 'stderr': stderr, 'timeout': timeout_encountered,
      'runtime': runtime, 'time_start': time_start, 'time_end': time_end
  }
  if stdin is not None:
    result.update({'stdin_bytes_sent': stdin.bytes_sent(), 'stdin_bytes_remain': stdin.bytes_remaining()})

  return result
