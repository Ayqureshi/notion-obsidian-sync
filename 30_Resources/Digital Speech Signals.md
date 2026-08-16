
- How can we take digital speech signals and characterise them from articulatory and acoustic perspectives?

Acoustic Phonetics
- the key to asr is using the information from the sound so we can map the sound without having to see the actual articulations
- Thicker darker bands show the formant
- Trade Offs frequency vs time resolution
	- increasing window we get better resolution
	- we can see better which frequencies are present in the input which is the narrow-band spectrogram
	- Conversely, when the window length is too small, we see more detail in time, but lose the ability to frequency detai ( so no more formants)

Hearing
- We as humans different parts of cochlea are sensitive to different frequents
- changes in pressure at different frequencies are detected and transmitted to the brain
- but for computers they don't have that
	- just like how sound creates pressure
	- we use discrete fourier transform to convert an sound clip which is time series of pressure(amplitude) into frequencies

Digital sound waves
- Microphone captures changes in air pressure to record sound which is then converted into a continuous electrical signal which we call analogue
- so the issue we face is that when this is done it needs to be done in binary but we need to convert the continuous sound recording into a digital representation
	- we do this by sampling the wave and storing these amplitude values in binary
- Analogue to digital conversion
	- in order to process we need to take this continous signal and make it into a series of discrete values
	- Sampling rate(samples/second = Hz), ie how many times we record a value from a wave
	- Sampling period = 1/sampling rate (seconds)

	Binary Representation - The number of bits you can use determines the precision with which you can represent the signal. as 1 bit is 2 values 2 bit is 4 values


	Quantization 
	- To give the waveform a binary representation, we need to map amplitudes to discrete bins and The number of bins determines how faithfully you can represent the wave
		- We need more bits if we want to capture a bigger dynamic range so 16 bits is ok
	-

	Aliasing
	- Frequencies above half the sampling rate (the Nyquist Frequency) will be indistinguishable from frequencies below the Nyquist frequency (i.e., the frequencies are aliased - you can’t tell what they really are!)
	- To be sure of our frequency analysis we first need to filter out high frequencies

	When generating a spectogram 
	- we need to filter out high frequencies
	Digitzation
	- start with ssampling and choosing the sampling rate
	- Then quantization and the amoutn of bits needed for this
	- A discrete representation in the time domain
	Discrete Fourier Transform
	- maps from time domain to frequency domain
	- applied to a short window(because of bits)
	- outputs magnitude and phase spectrum

Spectrogram: time vs frequency ‘heatmap’, where colour (darkness in Praat) corresponds to the ‘strength’ of different frequencies component in the signal.

## The Discrete Fourier Transform
So essentially it is a way to represent the frequency content of a discrete signal 

So for example we can look at a periodic function
- For function f which takes a time t as input, the output obeys: f(t) = f(t + nT)
- for some constant T (the period), for all times t and integers n The function outputs the same pattern over and over again
- A periodic function can be written as a discrete sum of simple periodic (sinusoidal) functions (i.e. sine and cosine) of different frequencies

what the fourier transform doess decompose a periodic waveform into a set of simple periodic functions
- If we scale and shift those puretones appropriately we can approximate the original waveform by adding the scaled and shifted waves together
-  It decomposes the time series waveform into component frequencies
- Non-zero magnitudes indicate that you would include that frequency in reconstructing the signal
- Magnitude spectrum is more so the relative loudness of the pure tones in the original signal

-> The input of it is a sequence of N values which are sampled amplitude values 

-> output is N complex numbers where N Correspond to N sinusoids with frequencies spread between 0 and the sampling rate
- The output coefficients tell us how to scale and shift the corresponding sinusoids so we can reconstruct the original input

	The complex number outputs can be interpreted in terms of:
		The magnitude spectrum: how much to scale the different pure tone frequency components
	The phase spectrum: how much to shift the different pure tone frequency components

So essentially the equation for the discrete fourier transform is the dot product of the input sequence and a complex sinusoid repeating at a specific frequency
- so when the frequency of input and basis sinusoid match (DFT[1] sinusoid “Basis sinusoid”) the dot product would be non zero even when doing a phase shift as Pairwise multiplication curve is not symmetric around zero
- but When the frequency of input and basis sinusoid are multiples of each other, the dot product is zero
- so when taking the input sequence x and the sinusoid associated with that and take the dot product of x and s 
- This measure tells us whether the input include a frequency component with the frequency as the sinusoid s k

Visualizing
- We describe points on the circle as Rejθ , where j=√-1 an imaginary number
- We describe points on the circle as Rejθ where R describes the magnitude of the vector and ፀ describes the angle of rotation (i.e., the phase) from (1,0)
- We now define sine and cosine in terms of the vector rotation
	- Sine is the vertical projection of the rotating vector
	- Cosine is the horizontal projection of the rotating vector
- The analysis frequencies are integer multiples of the first one. This means the (sampled) complex sinsuoids form are orthogonal: they have zero “similarity” to one another. This is
- what allows the DFT to pick out specific frequencies as being in the input signal


DFT to Spectogram
- Spectrogram is a series of DFTs in time: it creates a time-series of frequency domain features
- Real world signals are (sort of) locally periodic
- So, we perform the DFT on short regions and we got to remember type of window can change the output
- if input frequency falls between the outputs there will be the concept of leakage
- Positive magnitudes for the DFT outputs near the actual input frequency


Summary
- in order to analyze speech we need to digitze it through sampling it and quantiziing it
- and that in itself brings in constraints such as with the nyquist frequency being a limit to the frequencies we can record
- we also deal with alistasing making high frequencies seem like low ones

We then map from the time domain to the frequency domain using dft 
- Speech technologies use (variations of) the spectrogram to learn the relationship between speech, acoustics, and language automatically
- With enough complex sinusoids, we can approximate any function to basically an arbitrary degree of precision.

