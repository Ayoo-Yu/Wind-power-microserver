import axios from 'axios'

export function resurrectService() {
  return axios({
    url: '/api/resurrect',
    method: 'post'
  })
} 