import numpy as np


class OverlapSave:
    # N-point overlap-save.
    # convolve SISO FIR to all channels in parallel.
    # fir.ndim shoud be 1.
    # schedule: step of delay (schedule * N taps)
    
    def __init__(self, fir, N, channel=1, schedule=0, dtype=np.float32):
    
        if fir.ndim != 1:
            raise Exception('invalid fir shape')

        self.N = N
        self.len_fir = len(fir)
        fir_zeropad = np.zeros(2 * N, dtype=dtype)
        fir_zeropad[N:N + self.len_fir] = fir

        self.fir_f = np.fft.rfft(fir_zeropad)
        self.x = np.zeros([channel, 2 * N], dtype=dtype)
        self.y_buff = np.zeros([schedule + 1, channel, N], dtype=dtype)
        self.i_buff = 0

        self.len_y = fir.shape[-1]
        self.len_y_buff = np.empty([schedule + 1], dtype=np.int)
        self.len_y_buff[:] = N
        
        self.schedule = schedule


    def conv(self, x):
        
        # shifted into buffer
        len_x = x.shape[-1]
        self.x[:, :self.N] = self.x[:, self.N:]
        self.x[:, self.N:self.N + len_x] = x
        self.x[:, self.N + len_x:] = 0
        
        # convolution
        X = np.fft.rfft(self.x)
        self.y_buff[self.i_buff] = np.fft.irfft(self.fir_f * X)[:, :self.N]

        # length of output
        if len_x != 0:
            self.len_y = len_x + self.len_fir - 1
            
        elif self.len_y:
            self.len_y -= self.N
            if self.len_y < 0:
                self.len_y = 0

        if self.len_y > self.N:
            self.len_y_buff[self.i_buff] = self.N
        else:
            self.len_y_buff[self.i_buff] = self.len_y

        # ring buffer for delay of y
        self.i_buff += 1
        if self.i_buff > self.schedule:
            self.i_buff = 0
                
        return self.y_buff[self.i_buff], self.len_y_buff[self.i_buff]
    

    def clear(self):
        self.x[:] = 0
        self.y_buff[:] = 0



class OverlapSaveMIMO:
    # N-point overlap-save.
    # convolve MIMO FIR to all channels in parallel.
    # fir.ndim shoud be 3.
    # schedule: step of delay (schedule * N taps)
    
    def __init__(self, fir, N, schedule=0, dtype=np.float32):

        if fir.ndim != 3:
            raise Exception('invalid fir shape')
        
        ch_out = fir.shape[0]
        ch_in = fir.shape[1]
        self.len_fir = fir.shape[2]

        self.N = N
        fir_zeropad = np.zeros([ch_out, ch_in, 2 * N], dtype=dtype)
        fir_zeropad[:, :, N:N + self.len_fir] = fir

        self.fir_f = np.fft.rfft(fir_zeropad).transpose(2, 0, 1)
        self.x = np.zeros([ch_in, 1, 2 * N], dtype=dtype)
        self.y_buff = np.zeros([schedule + 1, ch_out, N], dtype=dtype)
        self.i_buff = 0

        self.len_y = fir.shape[-1]
        self.len_y_buff = np.empty([schedule + 1], dtype=np.int)
        self.len_y_buff[:] = N
        
        self.schedule = schedule


    def conv(self, x):
        
        # shifted into buffer
        len_x = x.shape[-1]
        self.x[:, 0, :self.N] = self.x[:, 0, self.N:]
        self.x[:, 0, self.N:self.N + len_x] = x
        self.x[:, 0, self.N + len_x:] = 0
        
        # convolution
        x_f = np.fft.rfft(self.x).transpose(2, 0, 1)
        y_f = np.matmul(self.fir_f, x_f).transpose(1, 2, 0)
        self.y_buff[self.i_buff] = np.fft.irfft(y_f)[:, 0, :self.N]

        # length of output
        if len_x != 0:
            self.len_y = len_x + self.len_fir - 1
            
        elif self.len_y:
            self.len_y -= self.N
            if self.len_y < 0:
                self.len_y = 0

        if self.len_y > self.N:
            self.len_y_buff[self.i_buff] = self.N
        else:
            self.len_y_buff[self.i_buff] = self.len_y

        # ring buffer for delay of y
        self.i_buff += 1
        if self.i_buff > self.schedule:
            self.i_buff = 0
                
        return self.y_buff[self.i_buff], self.len_y_buff[self.i_buff]
    

    def clear(self):
        self.x[:] = 0
        self.y_buff[:] = 0




if __name__ == '__main__':

    import matplotlib.pyplot as plt
    
    # ----- convolve using OverlapSave() -----

    # input signal and FIR
    src = np.ones(100).reshape(1, -1)
    fir = np.ones(40)
    N = 32
    
    # split FIR
    n_ch = src.shape[0]
    len_fir = len(fir)
    len_out = src.shape[-1] + len_fir - 1
    n_split = int(np.ceil(len_fir / N))
    fir_n = []
    for i in range(n_split):
        ss = N * i
        to = ss + N
        if to > len_fir:
            to = len_fir
        
        os = OverlapSave(fir[ss:to], N, channel=n_ch, schedule=i)
        fir_n.append(os)
        print(i, fir[:, :, ss:to].shape)
    
    # convolution
    out = np.empty([n_ch, 0])
    out_n = np.empty([n_ch, N])

    ss = 0
    to = ss + N
    while True:
        out_n[:] = 0
        for n in range(n_split):
            out_n_, L = fir_n[n].conv(src[:, ss:to])
            out_n += out_n_
        out = np.c_[out, out_n[:, :L]]

        if L < N:
            break
        ss += N
        to += N
    
    print(out.shape)
    for i in range(out.shape[0]):
        plt.subplot(out.shape[0], 1, i + 1)
        plt.plot(out[i, :], lw=1)
    plt.show()
    
    

    # ----- convolve using OverlapSaveMIMO() -----

    # input signal and FIR
    src = np.ones(100).reshape(1, -1)
    fir = np.zeros([2, 1, 40]) # 1in/2out
    N = 32

    # split FIR
    n_ch = src.shape[0]
    len_fir = fir.shape[-1]
    len_out = src.shape[-1] + len_fir - 1
    n_split = int(np.ceil(len_fir / N))
    fir_n = []
    for i in range(n_split):
        ss = N * i
        to = ss + N
        if to > len_fir:
            to = len_fir

        os = OverlapSaveMIMO(fir[:, :, ss:to], N, schedule=i)
        fir_n.append(os)
        print(i, fir[:, :, ss:to].shape)

    # convolution
    out = np.empty([fir.shape[0], 0])
    out_n = np.empty([fir.shape[0], N])

    ss = 0
    to = ss + N
    while True:
        out_n[:] = 0
        for n in range(n_split):
            out_n_, L = fir_n[n].conv(src[:, ss:to])
            out_n += out_n_
        out = np.c_[out, out_n[:, :L]]

        if L < N:
            break
        ss += N
        to += N

    print(out.shape)
    for i in range(out.shape[0]):
        plt.subplot(out.shape[0], 1, i + 1)
        plt.plot(out[i, :], lw=1)
    plt.show()
    
