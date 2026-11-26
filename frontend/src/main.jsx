import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './styles.css'
import { activarOndas } from './agua.js'

activarOndas()

createRoot(document.getElementById('root')).render(<App />)
