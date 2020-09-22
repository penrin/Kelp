import numpy as np
import matplotlib.pyplot as plt


dtype_float = {'float': np.float32, 'double':np.float64}
dtype_complex = {'float': np.complex64, 'double':np.complex128}


class OverlapSave:
    # N-point overlap-save convolution
    # 
    # SISO FIR is applied in parallel to all channels.
    # fir.ndim should be 1.
    # FIR longer than N is automatically chunked.

    def __init__(self, fir, N, channel, dtype='float'):
        if fir.ndim != 1:
            raise Exception('invalid fir shape')

        self.N = N
        self.len_fir = fir.shape[-1]

        # split FIR
        fir_split = []
        ss = 0
        while ss < fir.shape[-1]:
            fir_split.append(fir[ss:ss + N])
            ss += N
        
        # instantiate convolver
        self.c = []
        for i in range(len(fir_split)):
            self.c.append(_Convolver(fir_split[i], N, channel, i, dtype))
        
        # input buffer
        dt_r = dtype_float[dtype]
        self.in_buf = np.zeros([channel, 2 * N], dtype=dt_r)
        
        # output
        dt_c = dtype_complex[dtype]
        self.out_f = np.zeros([channel, N + 1], dtype=dt_c)

        # buffering length
        self.len_buf = self.N
        
    def conv(self, x):

        # shifted into buffer
        len_in = x.shape[-1]
        self.in_buf[:, :self.N] = self.in_buf[:, self.N:]
        self.in_buf[:, self.N:self.N + len_in] = x
        self.in_buf[:, self.N + len_in:] = 0

        # convolution
        in_f = np.fft.rfft(self.in_buf)
        self.out_f[:] = 0
        for c_ in self.c:
            self.out_f[:] += c_.conv(in_f)
        out = np.fft.irfft(self.out_f)[:, :self.N]

        # buffering length
        if len_in != 0:
            self.len_buf = self.len_fir + len_in - 1
        else:
            self.len_buf -= self.N

        return out, self.len_buf
            
    
    def clear_buffer(self):
        for c_ in self.c:
            c_.out_f_buf[:] = 0


class _Convolver:

    def __init__(self, fir, N, channel, schedule, dtype):
        self.N = N
        self.schedule = schedule

        # FIR (frequency domain)
        dt_r = dtype_float[dtype]
        fir_zeropad = np.zeros(2 * N, dtype=dt_r)
        fir_zeropad[N:N + fir.shape[-1]] = fir
        self.fir_f = np.fft.rfft(fir_zeropad)
        
        # output buffer delay output timing by N * schedule
        dt_c = dtype_complex[dtype]
        self.out_f_buf = np.zeros([schedule + 1, channel, N + 1], dtype=dt_c)
        self.i_buf = 0
        
    def conv(self, x_f):
        # convolution
        self.out_f_buf[self.i_buf] = self.fir_f * x_f
        # index ring buffer
        self.i_buf += 1
        if self.i_buf > self.schedule:
            self.i_buf = 0
        return self.out_f_buf[self.i_buf]






class OverlapSaveMIMO:
    # N-point overlap-save convolution
    # 
    # MIMO FIR is applied.
    # fir.ndim should be 1.
    # FIR longer than N is automatically chunked.

    def __init__(self, fir, N, dtype=np.float32):
        if fir.ndim != 3:
            raise Exception('invalid fir shape')

        self.N = N
        self.len_fir = fir.shape[-1]

        ch_out = fir.shape[0]
        ch_in = fir.shape[1]

        # split FIR
        fir_split = []
        ss = 0
        while ss < fir.shape[-1]:
            fir_split.append(fir[:, :, ss:ss + N])
            ss += N
        
        # instantiate convolver
        self.c = []
        for i in range(len(fir_split)):
            self.c.append(_ConvolverMIMO(fir_split[i], N, i, dtype))
        
        # input buffer
        dt_r = dtype_float[dtype]
        self.in_buf = np.zeros([ch_in, 1, 2 * N], dtype=dt_r)
        
        # output
        dt_c = dtype_complex[dtype]
        self.out_f = np.zeros([ch_out, N + 1], dtype=dt_c)

        # buffering length
        self.len_buf = self.N


    def conv(self, x):

        # shifted into buffer
        len_in = x.shape[-1]
        self.in_buf[:, 0, :self.N] = self.in_buf[:, 0, self.N:]
        self.in_buf[:, 0, self.N:self.N + len_in] = x
        self.in_buf[:, 0, self.N + len_in:] = 0

        # convolution
        in_f = np.fft.rfft(self.in_buf).transpose(2, 0, 1)
        self.out_f[:] = 0
        for c_ in self.c:
            self.out_f[:] += c_.conv(in_f)
        out = np.fft.irfft(self.out_f)[:, :self.N]

        # buffering length
        if len_in != 0:
            self.len_buf = self.len_fir + len_in - 1
        else:
            self.len_buf -= self.N

        return out, self.len_buf
            
    
    def clear_buffer(self):
        for c_ in self.c:
            c_.out_f_buf[:] = 0


class _ConvolverMIMO:

    def __init__(self, fir, N, schedule, dtype):
        self.N = N
        self.schedule = schedule

        ch_out = fir.shape[0]
        ch_in = fir.shape[1]
        
        # FIR (frequency domain)
        dt_r = dtype_float[dtype]
        fir_zeropad = np.zeros([ch_out, ch_in, 2 * N], dtype=dt_r)
        fir_zeropad[:, :, N:N + fir.shape[-1]] = fir
        self.fir_f = np.fft.rfft(fir_zeropad).transpose(2, 0, 1)
        
        # output buffer delay output timing by N * schedule
        dt_c = dtype_complex[dtype]
        self.out_f_buf = np.zeros([schedule + 1, ch_out, N + 1], dtype=dt_c)
        self.i_buf = 0
        
    def conv(self, x_f):
        # convolution
        y_f = np.matmul(self.fir_f, x_f).transpose(1, 2, 0)
        self.out_f_buf[self.i_buf] = y_f[:, 0, :]
        # index ring buffer
        self.i_buf += 1
        if self.i_buf > self.schedule:
            self.i_buf = 0
        return self.out_f_buf[self.i_buf]





if __name__ == '__main__':
    
    import matplotlib.pyplot as plt
    
    
    # ----- convolve using OverlapSave() -----

    x = np.ones(80).reshape(1, -1)
    h = np.ones(40)
    N = 32
    dtype = 'float' # or 'double'

    os = OverlapSave(h, N, channel=x.shape[0], dtype=dtype)
    
    len_y = h.shape[-1] + x.shape[-1] - 1
    y = np.empty([x.shape[0], len_y], dtype=dtype)
    ss = 0
    while True:
        y_chunk, len_buf = os.conv(x[:, ss:ss + N])
        if len_buf <= 0:
            break

        L = np.clip(len_buf, 0, N)
        y[:, ss:ss + L] = y_chunk[:, :L]
        ss += N
         
    plt.plot(y[0], lw=1)
    plt.show()
    

    # ----- convolve using OverlapSaveMIMO() -----
    
    x = np.ones(160).reshape(2, -1)
    h = np.ones([2, 2, 40]) # 2in/2out
    N = 32
    dtype = 'float'
    
    os = OverlapSaveMIMO(h, N, dtype=dtype)
    
    len_y = h.shape[-1] + x.shape[-1] - 1
    y = np.empty([h.shape[0], len_y], dtype=dtype)
    ss = 0
    while True:
        y_chunk, len_buf = os.conv(x[:, ss:ss + N])
        if len_buf <= 0:
            break

        L = np.clip(len_buf, 0, N)
        y[:, ss:ss + L] = y_chunk[:, :L]
        ss += N
    
    plt.plot(y[0], lw=1)
    plt.show()


