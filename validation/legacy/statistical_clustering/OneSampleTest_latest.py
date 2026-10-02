import numpy as np
import datetime as dt
import os
from typing import List


class OneSampleTest:
    def __init__(self, start_time:List[int], end_time:List[int], min_magnitude:float, observation_days:int, reference_days:int, time_resolution:int, z_value:float, k:float) -> None:
        self.sT = dt.datetime(start_time[0], start_time[1], start_time[2])
        self.eT = dt.datetime(end_time[0], end_time[1], end_time[2])
        self.min_Mag = min_magnitude
        self.obs_days = observation_days
        self.ref_days = reference_days
        self.t_format = time_resolution
        self.z_value = z_value
        self.k = k

        self.sT_ordinal = self.sT.toordinal()
        self.eT_ordinal = self.eT.toordinal()
        self.total_days = (self.eT-self.sT).days+1

    def load_TEC_EQlist(self, dataset_path:str, place_name:str, location:List[float]) -> np.ndarray:
        download_path = os.path.join(dataset_path, f"{place_name}{self.sT.strftime('%Y%m%d')}_{self.eT.strftime('%Y%m%d')}")
        tec_1D = np.load(f'{download_path}/tec{location[0]}_{location[1]}.npy')
        EQ_list = np.load(f'{download_path}/eqlist.npy')
        
        tec_arr = np.reshape(tec_1D, (self.total_days, self.t_format))
        ordinal_dates = [dt.date(int(year), int(month), int(day)).toordinal() for year, month, day in EQ_list[:, :3]]
        EQ_list = np.hstack((EQ_list, np.array(ordinal_dates).reshape(-1, 1)))
        clean_EQ = self._filter_EQ(EQ_list)

        return tec_arr, clean_EQ

    def _filter_EQ(self, EQ_list:np.ndarray) -> np.ndarray:
        specific_EQ = EQ_list[EQ_list[:, -2] >= self.min_Mag]
        specific_EQ = specific_EQ[specific_EQ[:, -1] >= self.sT_ordinal + self.obs_days + self.ref_days]
        specific_EQ = specific_EQ[specific_EQ[:, -1] <= self.eT_ordinal - self.obs_days]

        return specific_EQ
        
    def process_population(self, tec_arr:np.ndarray) -> int:
        ref_arr = np.zeros((self.total_days-self.ref_days, self.t_format, self.ref_days), dtype=float)
        for i in range(self.ref_days):
            ref_arr[:, :, i] = tec_arr[i:i+self.total_days-self.ref_days]

        obs_pop = tec_arr[self.ref_days:]

        [q1_pop, q2_pop, q3_pop] = np.percentile(ref_arr, [25, 50, 75], axis=2)
        ub_pop = q2_pop + self.k*(q3_pop - q2_pop)
        lb_pop = q2_pop - self.k*(q2_pop - q1_pop)

        pos_pop = np.sum(obs_pop > ub_pop)
        neg_pop = np.sum(obs_pop < lb_pop)

        return pos_pop, neg_pop

    def process_subset(self, tec_arr:np.ndarray, clean_EQ:np.ndarray) -> np.ndarray:
        ref_arr = np.zeros((self.obs_days*2+1, self.t_format, self.ref_days), dtype=float)
        obs = np.zeros((self.obs_days*2+1, self.t_format, clean_EQ.shape[0]), dtype=float)
        q1, q2, q3 = np.zeros_like(obs), np.zeros_like(obs), np.zeros_like(obs)

        for idx, ordinal_date in enumerate(clean_EQ[:, -1]):
            posi = int(ordinal_date-(self.obs_days+self.ref_days)-self.sT_ordinal)
            tec_temp = tec_arr[posi:posi+(self.ref_days+self.obs_days*2)+1]
            for i in range(self.ref_days):
                ref_arr[:, :, i] = tec_temp[i:i+tec_temp.shape[0]-self.ref_days]

            [q1_temp, q2_temp, q3_temp] = np.percentile(ref_arr, [25, 50, 75], axis=2)
            obs[:, :, idx] = tec_temp[self.ref_days:]
            q1[:, :, idx], q2[:, :, idx], q3[:, :, idx] = q1_temp, q2_temp, q3_temp

        delta_tec = obs - q2
        ub, lb = q2 + self.k * (q3 - q2), q2 - self.k * (q2 - q1)
        pos_sub = np.sum((obs - ub) > 0, axis=2)
        neg_sub = np.sum((obs - lb) < 0, axis=2)

        return pos_sub, neg_sub, delta_tec

    def process_Z_score(self, pos_sub:np.ndarray, neg_sub:np.ndarray, pos_pop:int, neg_pop:int, clean_EQ:np.ndarray) -> np.ndarray:
        p_pos = pos_sub/clean_EQ.shape[0]
        p0_pos = pos_pop/self.t_format/(self.total_days-self.ref_days)
        z_pos = (p_pos-p0_pos)/(np.sqrt(p0_pos*(1-p0_pos)/clean_EQ.shape[0]))

        p_neg = neg_sub/clean_EQ.shape[0]
        p0_neg = neg_pop/self.t_format/(self.total_days-self.ref_days)
        z_neg = (p_neg-p0_neg)/(np.sqrt(p0_neg*(1-p0_neg)/clean_EQ.shape[0]))

        return z_pos, z_neg

    def generate_mask(self, z_pos:np.ndarray, z_neg:np.ndarray) -> np.ndarray:
        """
        We only return the binary values at the time points that passed the statistical test.
        """
        pos_arr = np.where(z_pos > self.z_value, 1, 0)
        neg_arr = np.where(z_neg > self.z_value, -1, 0)
        mask_arr = pos_arr + neg_arr

        return mask_arr

    def operate(self, dataset_path:str, place_name:str, location:List[float]) -> np.ndarray:
        tec_arr, clean_EQ = self.load_TEC_EQlist(dataset_path, place_name, location)
        pos_pop, neg_pop = self.process_population(tec_arr)
        pos_sub, neg_sub, delta_tec = self.process_subset(tec_arr, clean_EQ)
        z_pos, z_neg = self.process_Z_score(pos_sub, neg_sub, pos_pop, neg_pop, clean_EQ)
        mask_arr = self.generate_mask(z_pos, z_neg)

        return clean_EQ, z_pos, z_neg, delta_tec, mask_arr


if __name__ == '__main__':
    print('----- Call it locally -----')
    dataset_path = 'I:/IRSL/GIMTEC_interpolation_py'
    place_name = 'Afghanistan'
    location = [33.092, 69.514]

    start_time = [1999, 1, 1]
    end_time = [2021, 12, 31]
    min_magnitude = 6.0
    observation_days = 30
    reference_days = 15
    time_resolution = 24
    z_value = 1.96
    k = 3

    ost = OneSampleTest(start_time, end_time, min_magnitude, observation_days, reference_days, time_resolution, z_value, k)
    clean_EQ, z_pos, z_neg, delta_tec, mask_arr = ost.operate(dataset_path, place_name, location)

