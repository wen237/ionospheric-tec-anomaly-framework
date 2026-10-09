import numpy as np
import datetime as dt
import scipy.io as sio
import math
import matplotlib as mpl
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.patches import Circle
from matplotlib.axes import Axes
from matplotlib.colors import ListedColormap
from matplotlib import colormaps
from matplotlib.figure import Figure


class SpatialSearch:
    def __init__(self, dataset_path:list[str], start_time:list[int], end_time:list[int], location:list[float], magnitude:float, reference_days:int, k:float) -> None:
        self.dataset_path = dataset_path
        self.sT = dt.datetime(start_time[0], start_time[1], start_time[2], start_time[3], 0, 0)
        self.eT = dt.datetime(end_time[0], end_time[1], end_time[2], end_time[3], 0, 0)

        self.location = location
        self.pd_radii = pow(10, magnitude*0.43)

        self.ref_days = reference_days
        self.k = k

    def _examine_date(self) -> None:
        if self.eT < dt.datetime(2014,10,19):
            self.t_format = 12
        elif self.sT-dt.timedelta(days=self.ref_days) > dt.datetime(2014,10,19):
            self.t_format = 24
        else:
            raise ValueError('The data format will be different!')

        if self.sT-dt.timedelta(days=self.ref_days) < dt.datetime(2002,11,3) and self.eT > dt.datetime(2002,11,3):
            raise ValueError('The data format will be different!')

    def load_TEC_info(self) -> tuple[np.ndarray, list[np.ndarray], dt.datetime, int]:
        self._examine_date()
        initial_day = self.sT - dt.timedelta(days=self.ref_days)
        total_days = self.eT.toordinal() - initial_day.toordinal() + 1

        tec_arr, time_ls = np.zeros((total_days*self.t_format, 71*73), dtype=float), []
        for i in range(total_days):
            day_increment = initial_day + dt.timedelta(days=i)
            year, doy = day_increment.year, day_increment.timetuple().tm_yday
            tec = np.load(f'{self.dataset_path[0]}{year}/gim{year}{doy:03}.npz')['gim']/10
            time = np.load(f'{self.dataset_path[0]}{year}/gim{year}{doy:03}.npz')['gim_time']

            tec = tec[:self.t_format*71]
            tec = self._examine_TEC(tec, day_increment)

            tec_arr[self.t_format*i:self.t_format*(i+1)] = np.reshape(tec, (self.t_format, 71*73))
            time_ls.append(time[:self.t_format])

        return tec_arr, time_ls, initial_day, total_days

    def _examine_TEC(self, tec:np.ndarray, date:dt.datetime) -> np.ndarray:
        if np.any(tec == 999.9):
            print(f'GIM shows 999.9 TECu at {date}.')
            tec[tec == 999.9] = None
        
        if np.any(tec == 0):
            print(f'GIM shows 0 TECu at {date}.')
            tec[tec == 0] = None

        return tec

    def rm_redundant_period(self, tec_arr:np.ndarray, time_ls:list[np.ndarray], initial_day:dt.datetime, total_days:int) -> tuple[np.ndarray, list[np.ndarray]]:
        if initial_day > dt.datetime(2014,10,19) and initial_day.hour != 0:
            tec_arr[:initial_day.hour] = None
            time_ls[0] = np.delete(time_ls[0], [np.arange(initial_day.hour)], 0)
            
        elif initial_day < dt.datetime(2014,10,19) and initial_day.hour != 0:
            tec_arr[:math.floor(initial_day.hour/2)] = None
            time_ls[0] = np.delete(time_ls[0], [np.arange(math.floor(initial_day.hour/2))], 0)

        if self.eT > dt.datetime(2014,10,19):
            tec_arr[(total_days-1)*self.t_format+self.eT.hour+1:] = None
            time_ls[-1] = np.delete(time_ls[-1], [np.arange(self.eT.hour+1, self.t_format, 1)], 0)
            
        elif self.eT < dt.datetime(2014,10,19):
            tec_arr[(total_days-1)*self.t_format+math.floor((self.eT.hour+2)/2):] = None
            time_ls[-1] = np.delete(time_ls[-1], [np.arange(math.floor((self.eT.hour+2)/2), self.t_format, 1)], 0)

        return tec_arr, time_ls

    def process_Pos_Neg_arr(self, clean_tec:np.ndarray, clean_time:list[np.ndarray], total_days:int) -> tuple[np.ndarray, list[np.ndarray]]:
        ref_arr = np.zeros(((total_days-self.ref_days)*self.t_format, 71*73, self.ref_days), dtype=float)
        for i in range(self.ref_days):
            ref_arr[:, :, i] = clean_tec[i*self.t_format:i*self.t_format+clean_tec.shape[0]-self.ref_days*self.t_format]

        obs_tec = clean_tec[self.ref_days*self.t_format:]
        q1, q2, q3 = np.nanpercentile(ref_arr, [25, 50, 75], axis=2)
        ub, lb = q2+self.k*(q3-q2), q2-self.k*(q2-q1)

        pos, neg = obs_tec-ub, obs_tec-lb
        pos[pos < 0], pos[pos > 0] = 0, 1
        neg[neg > 0], neg[neg < 0] = 0, 1

        pos, neg, specified_time = self._rm_excess_period(pos, neg, clean_time)
        pos_arr = np.nansum(pos, axis=0).reshape((71, 73))
        neg_arr = np.nansum(neg, axis=0).reshape((71, 73))

        return np.flipud(pos_arr), np.flipud(neg_arr), specified_time

    def _rm_excess_period(self, pos:np.ndarray, neg:np.ndarray, clean_time:list[np.ndarray]) -> tuple[np.ndarray, list[np.ndarray]]:
        if self.sT > dt.datetime(2014,10,19) and self.sT.hour != 0:
            pos[:self.sT.hour] = None
            neg[:self.sT.hour] = None
            clean_time[self.ref_days] = np.delete(clean_time[self.ref_days], [np.arange(self.sT.hour)], 0)

        elif self.sT < dt.datetime(2014,10,19) and self.sT.hour != 0:
            pos[:math.floor(self.sT.hour/2)] = None
            neg[:math.floor(self.sT.hour/2)] = None
            clean_time[self.ref_days] = np.delete(clean_time[self.ref_days], [np.arange(math.floor(self.sT.hour/2))], 0)

        return pos, neg, clean_time

    def convert_to_ratio(self, pos_arr:np.ndarray, neg_arr:np.ndarray, specified_time:list[np.ndarray]) -> np.ndarray:
        total_hrs = sum(i.shape[0] for i in specified_time[self.ref_days:])
        pos_ratio, neg_ratio = pos_arr/total_hrs*100, neg_arr/total_hrs*100

        key = input('How do you want to display the ratio matrix? normal(n) or clean(c): ')
        if key == 'c':
            print('Leave only the maximum values.')
            pos_ratio[pos_ratio != np.max(pos_ratio)] = None
            neg_ratio[neg_ratio != np.max(neg_ratio)] = None
        else:
            print('Display all values in matrix.')

        return pos_ratio, neg_ratio

    def operate(self) -> np.ndarray:
        tec_arr, time_ls, initial_day, total_days = self.load_TEC_info()
        clean_tec, clean_time = self.rm_redundant_period(tec_arr, time_ls, initial_day, total_days)
        pos_arr, neg_arr, specified_time = self.process_Pos_Neg_arr(clean_tec, clean_time, total_days)
        pos_ratio, neg_ratio = self.convert_to_ratio(pos_arr, neg_arr, specified_time)

        return pos_ratio, neg_ratio


class ShowSpatialResults(SpatialSearch):
    def __init__(self, dataset_path:list[str], start_time:list[int], end_time:list[int], location:list[float], magnitude:float, reference_days:int, k:float) -> None:
        super().__init__(dataset_path, start_time, end_time, location, magnitude, reference_days, k)
        self.magLat = sio.loadmat(f'{self.dataset_path[1]}/MagLat.mat').get('MagLat')
        self.magLon = np.arange(-180, 185, 5)
        self.lat_lon_series = [np.linspace(-87.5, 87.5, 71), np.linspace(-180, 180, 73)]
        
        self.axis_args = [0.12, 0.12, 0.75, 0.75]     # origin_x, origin_y, fig_length, fig_width
        self.extent_args = [-180, 180, -87.5, 87.5]     # x_min, x_max, y_min, y_max
        self.colorbar_args = [0.834, 0.12, 0.015, 0.75]    # cb_x, cb_y, cb_width, cb_length
        self.square_args = [5, 2.5]                           # width, height

    def plot_fig(self, arr:np.ndarray, polarity:str, mark_type:str) -> Figure:
        fig = plt.figure(figsize = (21, 9))
        mpl.rcParams['xtick.labelsize'] = 20
        mpl.rcParams['ytick.labelsize'] = 20
        mpl.rc('axes', linewidth = 2)

        proj = ccrs.PlateCarree()
        ax = fig.add_axes(self.axis_args, projection=proj)
        vmin, vmax = 0.0, np.nanmax(arr)
        custom_cmap = self._get_cmap()

        im = ax.imshow(arr, extent=self.extent_args, vmin=vmin, vmax=vmax, cmap=custom_cmap, origin='lower', interpolation='nearest', transform=proj, aspect='auto', zorder=1)
        ax.coastlines(resolution='110m', linewidth=0.8, zorder=2)
        ax.add_feature(cfeature.BORDERS, linestyle='--', linewidth=0.5, zorder=2)

        ax.plot(self.magLon, self.magLat[75], '--', color='darkred', lw=1.2, transform=proj, zorder=3)
        ax.plot(self.location[1], self.location[0], marker='*', mfc='yellow', mec='k', mew=1.8, ms=21, transform=proj, zorder=4)

        circle = Circle((self.location[1], self.location[0]), radius=self.pd_radii/111, fill=False, edgecolor='b', linewidth=2, zorder=4)
        ax.add_patch(circle)
        self._mark_peaks(mark_type, arr, ax, proj)

        ax.set_extent(self.extent_args, crs=proj)
        ax.set_xticks(np.arange(-150, 180, 30), crs=proj)
        ax.set_yticks(np.arange(-60, 90, 30), crs=proj)

        cb = self._add_colorbar(fig, im, vmax)            
        self._set_labels(polarity, ax, cb)

        ax.tick_params(axis='both', which='major', top=True, right=True, direction='in', length=7, width=2)
        ax.set_aspect('equal')

        # fig.savefig(f'I:/IRSL/Meeting/Afghanistan/2024/R1/SS_pos_1.png', dpi=800)

    def _get_cmap(self):
        base_cmap = colormaps['jet'](np.linspace(0, 1, 256))
        base_cmap[-1, :] = np.array([1.0, 0.0, 1.0, 1.0])
        custom_cmap = ListedColormap(base_cmap)

        return custom_cmap

    def _add_colorbar(self, fig:Figure, im, vmax:float):
        cb_ax = fig.add_axes(self.colorbar_args)
        cb = plt.colorbar(im, cax=cb_ax)
        rounded_max = round(vmax, 1)
        upper = int((rounded_max // 10) * 10)

        cb_ticks = list(range(0, upper + 1, 10)) + [rounded_max]
        cb.set_ticks(cb_ticks)
        cb.set_ticklabels([str(t) for t in cb_ticks])

        for t in cb.ax.get_yticklabels():
            if t.get_text() == f"{rounded_max}":
                t.set_color('magenta')
                t.set_fontweight('bold')
                t.set_size(20)

        return cb

    def _mark_peaks(self, types:str, arr:np.ndarray, ax:Axes, proj) -> None:
        peak_indices = np.where(arr == np.nanmax(arr))
        if types == '1':
            for i in range(len(peak_indices[0])):
                ax.plot(
                    self.lat_lon_series[1][peak_indices[1][i]], 
                    self.lat_lon_series[0][peak_indices[0][i]], 
                    'rs', markersize=18, alpha=0.85, 
                    transform=proj, zorder=5
                )
        elif types == '2':
            for i in range(len(peak_indices[0])):
                x0 = self.lat_lon_series[1][peak_indices[1][i]]-self.square_args[0]/2-0.96
                y0 = self.lat_lon_series[0][peak_indices[0][i]]-self.square_args[1]/2-0.42
                sq = plt.Rectangle(
                    (x0, y0), 
                    self.square_args[0], 
                    self.square_args[1], 
                    fill=True, 
                    facecolor=(1.0, 0.0, 1.0, 1.0), 
                    edgecolor='white', 
                    linewidth=1.5, 
                    transform=proj, 
                    zorder=5
                )
                ax.add_patch(sq)
        else:
            raise ValueError('Invalid character of arguments.')

    def _set_labels(self, polarity:str, ax:Axes, cb) -> None:
        label = [f'{polarity} TEC anomaly occurrence proportion ({self.sT.strftime("%Y-%m-%d")} to {self.eT.strftime("%Y-%m-%d")}, UT)', 'Longitude ('+u'\N{DEGREE SIGN}'+'E)', 
                 'Latitude ('+u'\N{DEGREE SIGN}'+'N)', 'Proportion of TEC anomalies (%)']
        ax.set_title(label[0], fontsize=20, fontweight='bold')
        ax.set_xlabel(label[1], fontsize=20)
        ax.set_ylabel(label[2], fontsize=20)
        cb.set_label(label[3], fontsize=20)

    def get_results(self) -> np.ndarray:
        pos_ratio, neg_ratio = self.operate()
        # self.plot_fig(pos_ratio, 'Positive', '2')
        self.plot_fig(neg_ratio, 'Negative', '2')
        plt.show()

        return pos_ratio, neg_ratio


if __name__ == '__main__':
    print('----- Call it locally -----')
    dataset_path = ['I:/IRSL/CODEGIM_FIN_py/GIMTEC', 'D:/matlab/MATLAB']

    start_time = [2022, 5, 28, 0, 0, 0]
    end_time = [2022, 6, 1, 23, 0, 0]

    location = [33.020, 69.464]    # [Latitude, Longitude]
    magnitude = 6.0

    pd_radii = pow(10, magnitude*0.43)    # Earthquake precursor deformation

    reference_days = 15
    k = 3

    ssr = ShowSpatialResults(dataset_path, start_time, end_time, location, magnitude, reference_days, k)
    pos_ratio, neg_ratio = ssr.get_results()

